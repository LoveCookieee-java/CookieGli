"""
Unit tests for CookieGli BoostEngine (Layer 1 static anchor & Layer 2 dynamic task tail).
"""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))

from cookiegli_core.boost_engine import BoostEngine, compute_reasoning_calibration
from cookiegli_core.mcp_server import CookieGliMcpServer
from cookiegli_core.genome_engine import estimate_tokens


class TestBoostEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.test_dir.name)
        self.cache_dir = self.root / '.cookiegli'

        # Set up a sample project structure
        src_dir = self.root / 'src'
        src_dir.mkdir(parents=True, exist_ok=True)

        (src_dir / 'cache_service.py').write_text(
            '"""Cache service module."""\n\n'
            'class CacheManager:\n'
            '    """Manages LRU and SQLite cache lookups."""\n\n'
            '    def resolve_cache_key(self, path: str, mtime: float) -> str:\n'
            '        """Resolve fast hashed cache key."""\n'
            '        return f"{path}:{mtime}"\n\n'
            '    def get(self, key: str) -> dict:\n'
            '        """Retrieve cached entry."""\n'
            '        return {}\n\n'
            '    def put(self, key: str, value: dict) -> None:\n'
            '        """Store cached entry."""\n'
            '        pass\n',
            encoding='utf-8'
        )

        (self.root / 'main.py').write_text(
            '"""Main runner."""\n'
            'from src.cache_service import CacheManager\n\n'
            'def run():\n'
            '    cm = CacheManager()\n'
            '    key = cm.resolve_cache_key("test.py", 123.0)\n'
            '    return key\n',
            encoding='utf-8'
        )

        tests_dir = self.root / 'tests'
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / 'test_cache_service.py').write_text(
            'import unittest\n'
            'from src.cache_service import CacheManager\n\n'
            'class TestCache(unittest.TestCase):\n'
            '    def test_key(self):\n'
            '        cm = CacheManager()\n'
            '        self.assertIsNotNone(cm.resolve_cache_key("a", 1.0))\n',
            encoding='utf-8'
        )

    def tearDown(self):
        try:
            self.test_dir.cleanup()
        except Exception:
            pass

    def test_reasoning_calibration_logic(self):
        """Verify calibration logic maps blast depth to LOW, MEDIUM, HIGH and 2026 models."""
        calib_low = compute_reasoning_calibration(1, "LOW")
        self.assertIn("effort: LOW", calib_low)
        self.assertIn("GPT-6 Astra", calib_low)
        self.assertIn("Claude Opus 5", calib_low)
        self.assertIn("Gemini 3.7 Flash", calib_low)
        self.assertIn("effort=low", calib_low)

        calib_med = compute_reasoning_calibration(2, "MEDIUM")
        self.assertIn("effort: MEDIUM", calib_med)
        self.assertIn("effort=medium", calib_med)

        calib_high = compute_reasoning_calibration(3, "CRITICAL")
        self.assertIn("effort: HIGH", calib_high)
        self.assertIn("effort=high", calib_high)

    def test_boost_init_project(self):
        """Verify boost --init scans codebase, populates cache & FTS5, and syncs Layer 1 static anchor."""
        with BoostEngine(str(self.root)) as engine:
            res = engine.init_project(target="all", max_tokens=600)
            self.assertEqual(res["status"], "success")
            self.assertGreaterEqual(res["total_files"], 3)
            self.assertTrue(bool(res["genome_hash"]))

        # Verify static files created
        claude_md = self.root / "CLAUDE.md"
        agents_md = self.root / "AGENTS.md"
        self.assertTrue(claude_md.exists())
        self.assertTrue(agents_md.exists())

        claude_text = claude_md.read_text(encoding='utf-8')
        self.assertIn("# PROJECT GENOME | id:", claude_text)
        self.assertIn("CacheManager", claude_text)

    def test_boost_idempotent_write_preserves_mtime(self):
        """Verify that running init_project multiple times does not bump mtime of target files if content unchanged."""
        with BoostEngine(str(self.root)) as engine:
            res1 = engine.init_project(target="all", max_tokens=600)

        claude_md = self.root / "CLAUDE.md"
        content1 = claude_md.read_text(encoding='utf-8')
        mtime_first = claude_md.stat().st_mtime_ns

        # Sleep slightly to ensure measurable mtime difference if re-written
        time.sleep(0.05)

        with BoostEngine(str(self.root)) as engine:
            res2 = engine.init_project(target="all", max_tokens=600)

        content2 = claude_md.read_text(encoding='utf-8')
        mtime_second = claude_md.stat().st_mtime_ns
        self.assertEqual(res1["genome_hash"], res2["genome_hash"], "Genome hashes differed!")
        self.assertEqual(content1, content2, "File contents differed!")
        self.assertEqual(mtime_first, mtime_second, "File mtime was modified despite identical content!")

    def test_synthesize_task_context_strict_token_bound(self):
        """Verify synthesize_task_context returns strictly <= 600 tokens."""
        with BoostEngine(str(self.root)) as engine:
            engine.init_project(target="all", max_tokens=600)
            context = engine.synthesize_task_context("Fix cache key generation in resolve_cache_key", max_tokens=600)

        tokens = estimate_tokens(context)
        self.assertLessEqual(tokens, 600)
        self.assertIn("[LAYER 2: DYNAMIC TASK TAIL", context)
        self.assertIn("[REASONING_CALIBRATION_2026]", context)
        self.assertIn("resolve_cache_key", context)
        self.assertIn("test_command:", context)

    def test_focus_symbol_verbatim_in_task_context(self):
        """Verify that targeted symbol is preserved verbatim with surrounding skeleton."""
        with BoostEngine(str(self.root)) as engine:
            engine.init_project(target="all", max_tokens=600)
            context = engine.synthesize_task_context("resolve_cache_key", max_tokens=600)

        self.assertIn("def resolve_cache_key", context)
        self.assertIn('return f"{path}:{mtime}"', context)

    def test_mcp_boost_and_search_tools(self):
        """Verify MCP server executes cookiegli_boost and cookiegli_search cleanly."""
        with BoostEngine(str(self.root)) as engine:
            engine.init_project(target="all", max_tokens=600)

        with CookieGliMcpServer(workspace_root=self.root) as server:
            # 1. Test cookiegli_boost
            boost_out = server.handle_tool_call(
                "cookiegli_boost",
                {"task": "resolve_cache_key", "max_tokens": 600}
            )
            self.assertIn("[LAYER 2: DYNAMIC TASK TAIL", boost_out)
            self.assertLessEqual(estimate_tokens(boost_out), 600)

            # 2. Test cookiegli_search
            search_out = server.handle_tool_call(
                "cookiegli_search",
                {"query": "CacheManager"}
            )
            self.assertIn("CacheManager", search_out)

    def test_cli_boost_and_search_commands(self):
        """Verify CLI boost --init, boost <task>, and search subcommands."""
        import io
        from contextlib import redirect_stdout
        from cli.cookiegli import cmd_boost, cmd_search
        import argparse

        # 1. boost --init
        args_init = argparse.Namespace(path=str(self.root), init=True, target='all', max_tokens=600, json=False, task='')
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = cmd_boost(args_init)
        self.assertEqual(ret, 0)
        self.assertIn("[BOOST INIT]", buf.getvalue())

        # 2. boost "<task>"
        args_task = argparse.Namespace(path=str(self.root), init=False, target='all', max_tokens=600, json=False, task='resolve_cache_key')
        buf2 = io.StringIO()
        with redirect_stdout(buf2):
            ret2 = cmd_boost(args_task)
        self.assertEqual(ret2, 0)
        self.assertIn("[COOKIEGLI BOOST]", buf2.getvalue())

        # 3. search "<query>"
        args_search = argparse.Namespace(root=str(self.root), query='CacheManager', limit=10, json=False)
        buf3 = io.StringIO()
        with redirect_stdout(buf3):
            ret3 = cmd_search(args_search)
        self.assertEqual(ret3, 0)
        self.assertIn("[FTS5 BM25 SEARCH]", buf3.getvalue())

    def test_synthesize_task_context_uninitialized_cache_auto_scan(self):
        """Verify that synthesize_task_context automatically scans codebase when cache is initially empty."""
        # Create fresh engine without calling init_project
        with BoostEngine(str(self.root)) as fresh_engine:
            self.assertEqual(fresh_engine.cache.count(), 0)
            context = fresh_engine.synthesize_task_context("resolve_cache_key", max_tokens=600)
            # Should have auto-scanned and found resolve_cache_key
            self.assertGreater(fresh_engine.cache.count(), 0)
            self.assertIn("resolve_cache_key", context)
            self.assertIn("CacheManager", context)

    def test_synthesize_task_context_empty_and_whitespace_task(self):
        """Verify empty and whitespace tasks are handled gracefully without errors."""
        with BoostEngine(str(self.root)) as engine:
            context_empty = engine.synthesize_task_context("", max_tokens=600)
            self.assertIn("[LAYER 2: DYNAMIC TASK TAIL", context_empty)
            self.assertLessEqual(estimate_tokens(context_empty), 600)

            context_ws = engine.synthesize_task_context("   \t\n  ", max_tokens=600)
            self.assertIn("[LAYER 2: DYNAMIC TASK TAIL", context_ws)
            self.assertLessEqual(estimate_tokens(context_ws), 600)

    def test_synthesize_task_context_very_small_token_budget_and_balanced_fences(self):
        """Verify very small token budgets strictly hold and markdown code fences remain balanced."""
        with BoostEngine(str(self.root)) as engine:
            engine.init_project(target="all", max_tokens=600)
            context = engine.synthesize_task_context("resolve_cache_key", max_tokens=150)
            self.assertLessEqual(estimate_tokens(context), 150)
            self.assertEqual(context.count("```") % 2, 0, "Markdown code fences must be balanced!")

    def test_multi_language_ambiguous_symbol_ranking(self):
        """Verify ranking and multi-hit retrieval when the same symbol exists in Python, TypeScript, and Go."""
        (self.root / 'resolver.ts').write_text(
            'export class DependencyResolver {\n'
            '    resolve(depId: string): boolean {\n'
            '        return true;\n'
            '    }\n'
            '}\n',
            encoding='utf-8'
        )
        (self.root / 'resolver.go').write_text(
            'package resolver\n\n'
            'type Resolver struct {}\n\n'
            'func (r *Resolver) Resolve(target string) error {\n'
            '    return nil\n'
            '}\n',
            encoding='utf-8'
        )

        with BoostEngine(str(self.root)) as engine:
            engine.init_project(target="all", max_tokens=600)
            results = engine.cache.search_bm25("resolve", limit=10)
            self.assertGreaterEqual(len(results), 2)
            names = [r["name"] for r in results]
            # Verify symbols from different languages are indexed
            self.assertTrue(any("resolve" in n.lower() for n in names))


    def test_boost_on_current_repo(self):
        """Verify cmd_boost works on the actual CookieGli repository without errors."""
        import io
        from contextlib import redirect_stdout
        from cli.cookiegli import cmd_boost
        import argparse

        # boost "AstCache" on REPO_ROOT
        args_task = argparse.Namespace(path=str(REPO_ROOT), init=False, target='all', max_tokens=600, json=False, task='AstCache search_bm25')
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = cmd_boost(args_task)
        self.assertEqual(ret, 0)
        output = buf.getvalue()
        self.assertIn("[COOKIEGLI BOOST]", output)
        self.assertIn("[REASONING_CALIBRATION_2026]", output)
        self.assertLessEqual(estimate_tokens(output), 650)

    def test_boost_init_on_current_repo(self):
        """Verify boost --init can run on current repo, producing byte-stable Token 0 static headers."""
        import io
        from contextlib import redirect_stdout
        from cli.cookiegli import cmd_boost
        import argparse

        args_init = argparse.Namespace(path=str(REPO_ROOT), init=True, target='all', max_tokens=600, json=False, task='')
        buf = io.StringIO()
        with redirect_stdout(buf):
            ret = cmd_boost(args_init)
        self.assertEqual(ret, 0)
        output = buf.getvalue()
        self.assertIn("[BOOST INIT]", output)

        claude_text = (REPO_ROOT / 'CLAUDE.md').read_text(encoding='utf-8')
        agents_text = (REPO_ROOT / 'AGENTS.md').read_text(encoding='utf-8')
        self.assertIn("# PROJECT GENOME | id:", claude_text)
        self.assertIn("# PROJECT GENOME | id:", agents_text)
        self.assertNotIn("(ROI:", claude_text)
        self.assertNotIn("(ROI:", agents_text)


if __name__ == '__main__':
    unittest.main()
