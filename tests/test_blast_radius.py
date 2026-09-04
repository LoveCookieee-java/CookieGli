"""
Unit tests for CookieGli Git Blast Radius & Downstream Dependency Analyzer.
Verifies forward-to-ingress graph inversion, multi-stage import resolution,
extension probing, deleted file resolution, circular dependency BFS safety,
git porcelain parsing, mtime pre-scan fallback, symbol targeting,
test command synthesis, hierarchical inside-out compaction, CLI, and MCP integration.
"""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))
sys.path.insert(0, str(REPO_ROOT / 'cli'))

from cookiegli_core.ast_scanner import AstScanner, CodeEntity, FileStructure
from cookiegli_core.cache_db import AstCache
from cookiegli_core.blast_radius import (
    BlastRadiusEngine,
    BlastRadiusReport,
    is_test_file,
    compute_impact_level,
)
from cookiegli_core.genome_engine import estimate_tokens
from cookiegli_core.mcp_server import CookieGliMcpServer
import cookiegli


class TestBlastRadius(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        self.cache_dir = self.root / '.cookiegli'

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_forward_to_ingress_graph_inversion(self):
        """1. Verify that forward imports (A -> B) are inverted to ingress graph (B -> {A})."""
        file_db = FileStructure(
            path=str(self.root / "src" / "db.py"),
            relative_path="src/db.py",
            language="Python",
            total_lines=10,
            classes=[CodeEntity(name="Database", entity_type="class", signature="class Database:")],
            imports_internal=[]
        )
        file_service = FileStructure(
            path=str(self.root / "src" / "service.py"),
            relative_path="src/service.py",
            language="Python",
            total_lines=20,
            functions=[CodeEntity(name="get_data", entity_type="function", signature="def get_data():")],
            imports_internal=["src.db"]
        )
        file_api = FileStructure(
            path=str(self.root / "src" / "api.py"),
            relative_path="src/api.py",
            language="Python",
            total_lines=30,
            functions=[CodeEntity(name="handler", entity_type="function", signature="def handler():")],
            imports_internal=["src.service"]
        )

        with BlastRadiusEngine(str(self.root), use_cache=False) as engine:
            ingress = engine.build_ingress_graph([file_db, file_service, file_api])

        self.assertIn("src/db.py", ingress)
        self.assertIn("src/service.py", ingress)
        self.assertIn("src/api.py", ingress)

        # Ingress: db.py is consumed by service.py
        self.assertIn("src/service.py", ingress["src/db.py"])
        # Ingress: service.py is consumed by api.py
        self.assertIn("src/api.py", ingress["src/service.py"])
        # api.py has no consumers
        self.assertEqual(len(ingress["src/api.py"]), 0)

    def test_multi_source_root_resolution_via_src(self):
        """2. Verify that imports like cookiegli_core.ast_scanner resolve to src/cookiegli_core/ast_scanner.py."""
        src_pkg = self.root / "src" / "my_pkg"
        src_pkg.mkdir(parents=True)
        (src_pkg / "__init__.py").write_text("", encoding="utf-8")
        (src_pkg / "core.py").write_text("class Core:\n    pass\n", encoding="utf-8")

        caller_file = self.root / "client.py"
        caller_file.write_text("from my_pkg.core import Core\n", encoding="utf-8")

        with BlastRadiusEngine(str(self.root), use_cache=False) as engine:
            with AstScanner(str(self.root), use_cache=False) as scanner:
                files = scanner.scan()
            ingress = engine.build_ingress_graph(files)

        self.assertIn("src/my_pkg/core.py", ingress)
        self.assertIn("client.py", ingress["src/my_pkg/core.py"])

    def test_extension_probing_resolution(self):
        """3. Verify candidate extension probing (.ts, .tsx, /index.ts) on extension-less imports."""
        src_dir = self.root / "src"
        src_dir.mkdir(parents=True)
        (src_dir / "utils.ts").write_text("export const add = (a: number, b: number) => a + b;\n", encoding="utf-8")
        
        comp_dir = src_dir / "Button"
        comp_dir.mkdir(parents=True)
        (comp_dir / "index.tsx").write_text("export const Button = () => null;\n", encoding="utf-8")

        app_file = self.root / "src" / "App.tsx"
        app_file.write_text(
            "import { add } from './utils';\n"
            "import { Button } from './Button';\n",
            encoding="utf-8"
        )

        with BlastRadiusEngine(str(self.root), use_cache=False) as engine:
            with AstScanner(str(self.root), use_cache=False) as scanner:
                files = scanner.scan()
            ingress = engine.build_ingress_graph(files)

        self.assertIn("src/utils.ts", ingress)
        self.assertIn("src/Button/index.tsx", ingress)
        self.assertIn("src/App.tsx", ingress["src/utils.ts"])
        self.assertIn("src/App.tsx", ingress["src/Button/index.tsx"])

    def test_deleted_file_resolution(self):
        """4. Verify that deleted target files injected into the resolver correctly connect consumers."""
        src_dir = self.root / "src"
        src_dir.mkdir(parents=True)

        consumer_file = src_dir / "consumer.py"
        consumer_file.write_text("import src.legacy_module\n", encoding="utf-8")

        deleted_file_rel = "src/legacy_module.py"
        # The file does NOT exist on disk!
        self.assertFalse((self.root / deleted_file_rel).exists())

        with BlastRadiusEngine(str(self.root), use_cache=False) as engine:
            report = engine.analyze(target_files=[deleted_file_rel])

        self.assertIn(deleted_file_rel, report.target_files)
        self.assertIn("src/consumer.py", report.direct_consumers)

    def test_circular_dependency_bfs_safety(self):
        """5. Verify that circular dependency cycles (A -> B -> C -> A) do not cause infinite loops."""
        src_dir = self.root / "src"
        src_dir.mkdir(parents=True)

        (src_dir / "cycle_a.py").write_text("import src.cycle_b\n", encoding="utf-8")
        (src_dir / "cycle_b.py").write_text("import src.cycle_c\n", encoding="utf-8")
        (src_dir / "cycle_c.py").write_text("import src.cycle_a\nimport src.cycle_d\n", encoding="utf-8")
        (src_dir / "cycle_d.py").write_text("import src.cycle_b\n", encoding="utf-8")

        with BlastRadiusEngine(str(self.root), use_cache=False) as engine:
            report = engine.analyze(target_files=["src/cycle_a.py"], max_depth=5)

        # BFS must terminate and correctly capture cycle
        self.assertIn("src/cycle_c.py", report.direct_consumers)
        self.assertTrue(report.total_fan_out >= 1)

    def test_git_status_porcelain_parsing(self):
        """6. Verify git status --porcelain parsing captures staged, unstaged, untracked, deleted, and renamed files."""
        porcelain_output = (
            "M  src/staged.py\n"
            " M src/unstaged.py\n"
            "MM src/both.py\n"
            "?? src/untracked.py\n"
            "D  src/deleted.py\n"
            " D src/unstaged_deleted.py\n"
            "R  src/old.py -> src/new.py\n"
            "!! cache/ignored.txt\n"
        )

        with BlastRadiusEngine(str(self.root), use_cache=False) as engine:
            changed = engine._parse_git_porcelain(porcelain_output)

        self.assertIn("src/staged.py", changed)
        self.assertIn("src/unstaged.py", changed)
        self.assertIn("src/both.py", changed)
        self.assertIn("src/untracked.py", changed)
        self.assertIn("src/deleted.py", changed)
        self.assertIn("src/unstaged_deleted.py", changed)
        self.assertIn("src/old.py", changed)
        self.assertIn("src/new.py", changed)
        self.assertNotIn("cache/ignored.txt", changed)

    def test_nongit_prescan_mtime_fallback(self):
        """7. Verify non-git pre-scan mtime comparison against SQLite cache detects modified, added, deleted files."""
        # Ensure no .git exists in root
        self.assertFalse((self.root / ".git").exists())

        src_dir = self.root / "src"
        src_dir.mkdir(parents=True)
        file_a = src_dir / "a.py"
        file_b = src_dir / "b.py"
        file_a.write_text("# initial A\n", encoding="utf-8")
        file_b.write_text("# initial B\n", encoding="utf-8")

        # Populate cache initially
        with AstCache(str(self.cache_dir)) as cache:
            struct_a = FileStructure(path=str(file_a), relative_path="src/a.py", language="Python")
            struct_b = FileStructure(path=str(file_b), relative_path="src/b.py", language="Python")
            cache.put(struct_a, mtime=file_a.stat().st_mtime, sha256="aaa")
            cache.put(struct_b, mtime=file_b.stat().st_mtime, sha256="bbb")
            cache.commit()

        # Modify file_a (change mtime)
        time.sleep(0.05)
        file_a.write_text("# modified A with new content\n", encoding="utf-8")
        os.utime(file_a, (time.time() + 10, time.time() + 10))

        # Delete file_b
        # Note: In test tearDown we clean up temp_dir, but here we intentionally delete a file inside our temp dir
        os.remove(file_b)

        # Add new file_c
        file_c = src_dir / "c.py"
        file_c.write_text("# new C\n", encoding="utf-8")

        with BlastRadiusEngine(str(self.root), use_cache=True) as engine:
            changed, source = engine.detect_changed_files()

        self.assertEqual(source, "mtime_cache")
        self.assertIn("src/a.py", changed)
        self.assertIn("src/b.py", changed)  # Detected deleted file
        self.assertIn("src/c.py", changed)  # Detected new file

    def test_explicit_file_and_symbol_targeting(self):
        """8. Verify explicit --file and --symbol targeting restricts the blast radius analysis."""
        src_dir = self.root / "src"
        src_dir.mkdir(parents=True)

        service_file = src_dir / "payment.py"
        service_file.write_text(
            "class PaymentGateway:\n"
            "    def charge(self, amount):\n"
            "        return True\n",
            encoding="utf-8"
        )

        client_file = src_dir / "checkout.py"
        client_file.write_text(
            "from src.payment import PaymentGateway\n"
            "def run():\n"
            "    return PaymentGateway().charge(10)\n",
            encoding="utf-8"
        )

        tests_dir = self.root / "tests"
        tests_dir.mkdir(parents=True)
        test_file = tests_dir / "test_payment.py"
        test_file.write_text(
            "import unittest\n"
            "from src.payment import PaymentGateway\n",
            encoding="utf-8"
        )

        # Test explicit file
        with BlastRadiusEngine(str(self.root), use_cache=False) as engine:
            report_file = engine.analyze(target_files=["src/payment.py"])

        self.assertEqual(report_file.detection_source, "explicit")
        self.assertEqual(report_file.target_files, ["src/payment.py"])
        self.assertIn("src/checkout.py", report_file.direct_consumers)
        self.assertIn("tests/test_payment.py", report_file.targeted_tests)

        # Test explicit symbol
        with BlastRadiusEngine(str(self.root), use_cache=False) as engine:
            report_sym = engine.analyze(symbol="PaymentGateway")

        self.assertEqual(report_sym.detection_source, "symbol")
        self.assertIn("src/payment.py", report_sym.target_files)
        self.assertIn("src/payment.py", report_sym.affected_symbols)
        self.assertEqual(report_sym.affected_symbols["src/payment.py"], ["PaymentGateway"])

    def test_surgical_test_command_synthesis(self):
        """9. Verify surgical test command synthesis probes pytest/unittest and falls back cleanly."""
        with BlastRadiusEngine(str(self.root), use_cache=False) as engine:
            # Fallback on empty tests
            cmd_empty = engine.synthesize_test_command([])
            self.assertEqual(cmd_empty, "python -m unittest discover -s tests")

            # With pytest available
            with patch("shutil.which", return_value="/usr/bin/pytest"):
                cmd_pytest = engine.synthesize_test_command(["tests/test_a.py", "tests/test_b.py"], lang="python")
                self.assertEqual(cmd_pytest, "pytest -v tests/test_a.py tests/test_b.py")

            # Without pytest (standard unittest)
            with patch("shutil.which", return_value=None):
                cmd_unittest = engine.synthesize_test_command(["tests/test_a.py", "tests/test_b.py"], lang="python")
                self.assertEqual(cmd_unittest, "python -m unittest tests/test_a.py tests/test_b.py")

            # Non-python languages
            cmd_ts = engine.synthesize_test_command(["src/app.test.ts"])
            self.assertEqual(cmd_ts, "npm test -- src/app.test.ts")

            cmd_go = engine.synthesize_test_command(["pkg/auth_test.go"])
            self.assertEqual(cmd_go, "go test pkg/auth_test.go")

    def test_hierarchical_inside_out_token_compaction(self):
        """10. Verify Hierarchical Inside-Out Compaction (< 250 tokens) keeps test command invariant."""
        targets = [f"src/module_{i}.py" for i in range(10)]
        directs = [f"src/consumer_direct_{i}.py" for i in range(12)]
        transit = [f"src/consumer_transitive_{i}.py" for i in range(25)]
        tests = ["tests/test_mod_0.py", "tests/test_mod_1.py"]
        symbols = {"src/module_0.py": ["FuncA", "ClassB"]}

        report = BlastRadiusReport(
            target_files=targets,
            impact_level="CRITICAL",
            direct_consumers=directs,
            transitive_consumers=transit,
            targeted_tests=tests,
            recommended_test_command="python -m unittest tests/test_mod_0.py tests/test_mod_1.py",
            affected_symbols=symbols,
            total_files=50,
            direct_fan_out=len(directs),
            total_fan_out=len(directs) + len(transit),
            fan_out_ratio=74.0,
            detection_source="explicit"
        )

        compact_250 = report.to_compact(max_tokens=250)
        tokens_250 = estimate_tokens(compact_250)
        self.assertLessEqual(tokens_250, 250)

        # INVARIANT: Header, Summary, Targeted Tests, and Recommended Test Command are NEVER truncated
        self.assertIn("[BLAST_RADIUS] Impact: CRITICAL", compact_250)
        self.assertIn("summary: Fan-out ratio:", compact_250)
        self.assertIn("targeted_tests:", compact_250)
        self.assertIn("tests/test_mod_0.py", compact_250)
        self.assertIn("recommended_test_command: python -m unittest tests/test_mod_0.py tests/test_mod_1.py", compact_250)

        # Transitive consumers truncated first
        self.assertIn("more)", compact_250)

        # Extreme budget: invariants MUST still hold
        compact_tight = report.to_compact(max_tokens=40)
        self.assertIn("[BLAST_RADIUS]", compact_tight)
        self.assertIn("targeted_tests:", compact_tight)
        self.assertIn("recommended_test_command: python -m unittest tests/test_mod_0.py tests/test_mod_1.py", compact_tight)

    def test_cli_cookiegli_blast(self):
        """11. Verify CLI cookiegli blast executes cleanly with text and --json flags."""
        src_dir = self.root / "src"
        src_dir.mkdir(parents=True)
        (src_dir / "target.py").write_text("class MyTarget:\n    pass\n", encoding="utf-8")
        (src_dir / "consumer.py").write_text("from src.target import MyTarget\n", encoding="utf-8")

        # Test text output via argparse
        parser = argparse_helper()
        args_text = parser.parse_args(["blast", "--path", str(self.root), "--file", "src/target.py"])
        
        with patch("sys.stdout.write") as mock_stdout, patch("builtins.print") as mock_print:
            ret = args_text.func(args_text)
            self.assertEqual(ret, 0)
            # Check print was called with blast radius output
            printed = [call.args[0] for call in mock_print.call_args_list if call.args]
            self.assertTrue(any("[BLAST_RADIUS]" in str(p) for p in printed))

        # Test json output
        args_json = parser.parse_args(["blast", "--path", str(self.root), "--file", "src/target.py", "--json"])
        with patch("builtins.print") as mock_print:
            ret = args_json.func(args_json)
            self.assertEqual(ret, 0)
            printed_json_str = mock_print.call_args[0][0]
            data = json.loads(printed_json_str)
            self.assertEqual(data["target_files"], ["src/target.py"])
            self.assertIn("src/consumer.py", data["direct_consumers"])
            self.assertEqual(data["detection_source"], "explicit")

    def test_mcp_cookiegli_blast_radius(self):
        """12. Verify MCP tool cookiegli_blast_radius execution and lock release."""
        src_dir = self.root / "src"
        src_dir.mkdir(parents=True)
        (src_dir / "alpha.py").write_text("def alpha():\n    return 1\n", encoding="utf-8")
        (src_dir / "beta.py").write_text("from src.alpha import alpha\n", encoding="utf-8")

        with CookieGliMcpServer(workspace_root=self.root) as server:
            manifest = server.get_tools_manifest()
            tool_names = [t["name"] for t in manifest]
            self.assertIn("cookiegli_blast_radius", tool_names)

            # Direct tool call
            result = server.handle_tool_call(
                "cookiegli_blast_radius",
                {"file": "src/alpha.py", "max_tokens": 250}
            )
            self.assertIn("[BLAST_RADIUS]", result)
            self.assertIn("targets: src/alpha.py", result)
            self.assertIn("direct_consumers: src/beta.py", result)
            self.assertIn("recommended_test_command:", result)

            # JSON-RPC protocol test
            rpc_req = {
                "jsonrpc": "2.0",
                "id": "test-blast-1",
                "method": "tools/call",
                "params": {
                    "name": "cookiegli_blast_radius",
                    "arguments": {"file": "src/alpha.py"}
                }
            }
            rpc_res = server.process_rpc_request(rpc_req)
            self.assertIsNotNone(rpc_res)
            self.assertEqual(rpc_res.get("id"), "test-blast-1")
            content = rpc_res["result"]["content"][0]["text"]
            self.assertIn("[BLAST_RADIUS]", content)

            # Test MCP tool with 'files' list argument
            result_files = server.handle_tool_call(
                "cookiegli_blast_radius",
                {"files": ["src/alpha.py"], "max_tokens": 250}
            )
            self.assertIn("[BLAST_RADIUS]", result_files)
            self.assertIn("targets: src/alpha.py", result_files)

    def test_find_tests_for_files_standalone(self):
        """13. Verify find_tests_for_files automatically discovers files when all_files is None."""
        src_dir = self.root / "src"
        tests_dir = self.root / "tests"
        src_dir.mkdir(parents=True)
        tests_dir.mkdir(parents=True)

        (src_dir / "user_service.py").write_text("class UserService: pass\n", encoding="utf-8")
        (tests_dir / "test_user_service.py").write_text("import unittest\n", encoding="utf-8")

        with BlastRadiusEngine(str(self.root), use_cache=False) as engine:
            found_tests = engine.find_tests_for_files(["src/user_service.py"])

        self.assertIn("tests/test_user_service.py", found_tests)

    def test_path_alias_import_resolution(self):
        """14. Verify path aliases like @/components/Button and ~/utils resolve through source roots."""
        src_dir = self.root / "src"
        (src_dir / "components").mkdir(parents=True)
        (src_dir / "components" / "Button.tsx").write_text("export const Button = () => null;\n", encoding="utf-8")
        (src_dir / "utils.ts").write_text("export const helper = () => 42;\n", encoding="utf-8")

        app_file = self.root / "src" / "App.tsx"
        app_file.write_text(
            "import { Button } from '@/components/Button';\n"
            "import { helper } from '~/utils';\n",
            encoding="utf-8"
        )

        with BlastRadiusEngine(str(self.root), use_cache=False) as engine:
            with AstScanner(str(self.root), use_cache=False) as scanner:
                files = scanner.scan()
            ingress = engine.build_ingress_graph(files)

        self.assertIn("src/components/Button.tsx", ingress)
        self.assertIn("src/utils.ts", ingress)
        self.assertIn("src/App.tsx", ingress["src/components/Button.tsx"])
        self.assertIn("src/App.tsx", ingress["src/utils.ts"])

    def test_root_level_caller_and_index_probing(self):
        """15. Verify that caller at root directory resolves imports without leading slashes."""
        src_dir = self.root / "src"
        src_dir.mkdir(parents=True)
        (src_dir / "index.ts").write_text("export const main = 1;\n", encoding="utf-8")

        root_caller = self.root / "entry.ts"
        root_caller.write_text("import { main } from './src';\n", encoding="utf-8")

        with BlastRadiusEngine(str(self.root), use_cache=False) as engine:
            with AstScanner(str(self.root), use_cache=False) as scanner:
                files = scanner.scan()
            ingress = engine.build_ingress_graph(files)

        self.assertIn("src/index.ts", ingress)
        self.assertIn("entry.ts", ingress["src/index.ts"])

    def test_cli_main_entrypoint_direct(self):
        """16. Verify calling cookiegli.main() directly with patched sys.argv works."""
        src_dir = self.root / "src"
        src_dir.mkdir(parents=True)
        (src_dir / "app.py").write_text("def run(): pass\n", encoding="utf-8")

        test_argv = ["cookiegli", "blast", "--path", str(self.root), "--file", "src/app.py"]
        with patch.object(sys, "argv", test_argv), patch("builtins.print") as mock_print:
            code = cookiegli.main()
            self.assertEqual(code, 0)
            printed = [c.args[0] for c in mock_print.call_args_list if c.args]
            self.assertTrue(any("[BLAST_RADIUS]" in str(p) for p in printed))

    def test_analyze_with_explicit_empty_target_files(self):
        """17. Verify analyze(target_files=[]) returns clean empty report without calling git."""
        with BlastRadiusEngine(str(self.root), use_cache=False) as engine:
            report = engine.analyze(target_files=[])

        self.assertEqual(report.target_files, [])
        self.assertEqual(report.direct_consumers, [])
        self.assertEqual(report.transitive_consumers, [])
        self.assertEqual(report.detection_source, "explicit")


def argparse_helper():
    """Builds a test CLI argument parser matching main()."""
    import argparse
    parser = argparse.ArgumentParser(prog='cookiegli')
    subparsers = parser.add_subparsers(dest='command', required=True)
    p_blast = subparsers.add_parser('blast')
    p_blast.add_argument('--diff', action='store_true')
    p_blast.add_argument('--symbol')
    p_blast.add_argument('--file')
    p_blast.add_argument('--path', default='.')
    p_blast.add_argument('--max-depth', type=int, default=3)
    p_blast.add_argument('--json', action='store_true')
    p_blast.add_argument('--no-cache', action='store_true')
    p_blast.set_defaults(func=cookiegli.cmd_blast)
    return parser


if __name__ == '__main__':
    unittest.main()
