"""
Unit tests for CookieGli Symbol Cache, Method Extraction, and Multi-Source Root Resolution.
"""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))

from cookiegli_core.ast_scanner import AstScanner, CodeEntity, FileStructure
from cookiegli_core.cache_db import AstCache
from cookiegli_core.mcp_server import CookieGliMcpServer
from cookiegli_core.monorepo_engine import MonorepoEngine


class TestSymbolCache(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.cache_dir = self.root / '.cookiegli'

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_multi_source_root_resolution(self):
        """Verify that internal packages under src/ are recognized as internal imports."""
        src_dir = self.root / 'src' / 'my_internal_pkg'
        src_dir.mkdir(parents=True)
        (src_dir / '__init__.py').write_text("# package init\n", encoding='utf-8')
        (src_dir / 'service.py').write_text("class MyService:\n    pass\n", encoding='utf-8')

        # Test file that imports my_internal_pkg and an external pkg
        test_file = self.root / 'main.py'
        test_file.write_text(
            "import os\n"
            "import requests\n"
            "from my_internal_pkg.service import MyService\n",
            encoding='utf-8'
        )

        with AstScanner(str(self.root), use_cache=False) as scanner:
            results = scanner.scan()

        main_struct = next((r for r in results if r.relative_path == 'main.py'), None)
        self.assertIsNotNone(main_struct)
        self.assertIn('my_internal_pkg.service', main_struct.imports_internal)
        self.assertIn('requests', main_struct.imports_external)
        self.assertNotIn('os', main_struct.imports_external)

    def test_method_extraction_python(self):
        """Verify that Python class methods are extracted with container prefix in FileStructure.methods."""
        py_code = (
            "class MathService:\n"
            "    \"\"\"Math service docstring.\"\"\"\n"
            "    def __init__(self, seed: int = 0):\n"
            "        self.seed = seed\n"
            "\n"
            "    def calculate(self, x: int, y: int) -> int:\n"
            "        \"\"\"Calculate sum.\"\"\"\n"
            "        return x + y\n"
            "\n"
            "    async def async_fetch(self, key: str) -> dict:\n"
            "        return {}\n"
        )
        (self.root / 'math_service.py').write_text(py_code, encoding='utf-8')

        with AstScanner(str(self.root), use_cache=False) as scanner:
            results = scanner.scan()

        struct = next((r for r in results if r.relative_path == 'math_service.py'), None)
        self.assertIsNotNone(struct)

        # Classes
        self.assertEqual(len(struct.classes), 1)
        self.assertEqual(struct.classes[0].name, 'MathService')
        self.assertIn('calculate', struct.classes[0].signature)

        # Methods
        method_names = [m.name for m in struct.methods]
        self.assertIn('MathService.__init__', method_names)
        self.assertIn('MathService.calculate', method_names)
        self.assertIn('MathService.async_fetch', method_names)

        calc_m = next(m for m in struct.methods if m.name == 'MathService.calculate')
        self.assertEqual(calc_m.entity_type, 'method')
        self.assertEqual(calc_m.docstring, 'Calculate sum.')
        self.assertIn('def calculate', calc_m.signature)

    def test_method_extraction_go(self):
        """Verify that Go receiver methods are extracted as Receiver.Method."""
        go_code = (
            "package main\n\n"
            "type Worker struct {\n"
            "    ID int\n"
            "}\n\n"
            "func (w *Worker) ProcessTask(task string) (bool, error) {\n"
            "    return true, nil\n"
            "}\n\n"
            "func StandaloneFunc(n int) int {\n"
            "    return n * 2\n"
            "}\n"
        )
        (self.root / 'worker.go').write_text(go_code, encoding='utf-8')

        with AstScanner(str(self.root), use_cache=False) as scanner:
            results = scanner.scan()

        struct = next((r for r in results if r.relative_path == 'worker.go'), None)
        self.assertIsNotNone(struct)

        method_names = [m.name for m in struct.methods]
        func_names = [f.name for f in struct.functions]

        self.assertIn('Worker.ProcessTask', method_names)
        self.assertNotIn('Worker.ProcessTask', func_names)
        self.assertIn('StandaloneFunc', func_names)

    def test_method_extraction_typescript(self):
        """Verify that TypeScript class methods are extracted into structure.methods."""
        ts_code = (
            "export class OrderProcessor {\n"
            "    constructor() {}\n"
            "    public async processOrder(orderId: string): Promise<boolean> {\n"
            "        return true;\n"
            "    }\n"
            "    cancelOrder(orderId: string) {\n"
            "        return false;\n"
            "    }\n"
            "}\n"
            "export function helper() {}\n"
        )
        (self.root / 'orders.ts').write_text(ts_code, encoding='utf-8')

        with AstScanner(str(self.root), use_cache=False) as scanner:
            results = scanner.scan()

        struct = next((r for r in results if r.relative_path == 'orders.ts'), None)
        self.assertIsNotNone(struct)

        method_names = [m.name for m in struct.methods]
        self.assertIn('OrderProcessor.processOrder', method_names)
        self.assertIn('OrderProcessor.cancelOrder', method_names)

        func_names = [f.name for f in struct.functions]
        self.assertIn('helper', func_names)

    def test_rust_keyword_imports_and_java_methods(self):
        """Verify Rust crate/super/self are categorized as internal and Java methods are extracted."""
        rust_code = (
            "use crate::models::User;\n"
            "use super::utils;\n"
            "use self::submod;\n"
            "use serde::Deserialize;\n"
        )
        (self.root / 'lib.rs').write_text(rust_code, encoding='utf-8')

        java_code = (
            "package com.app;\n\n"
            "public class PaymentGateway {\n"
            "    public boolean charge(double amount) {\n"
            "        return true;\n"
            "    }\n"
            "}\n"
        )
        (self.root / 'PaymentGateway.java').write_text(java_code, encoding='utf-8')

        with AstScanner(str(self.root), use_cache=False) as scanner:
            results = scanner.scan()

        rs_struct = next((r for r in results if r.relative_path == 'lib.rs'), None)
        self.assertIsNotNone(rs_struct)
        self.assertIn('crate::models::User', rs_struct.imports_internal)
        self.assertIn('super::utils', rs_struct.imports_internal)
        self.assertIn('self::submod', rs_struct.imports_internal)
        self.assertIn('serde', rs_struct.imports_external)

        java_struct = next((r for r in results if r.relative_path == 'PaymentGateway.java'), None)
        self.assertIsNotNone(java_struct)
        java_methods = [m.name for m in java_struct.methods]
        self.assertIn('PaymentGateway.charge', java_methods)

    def test_cache_hit_with_relative_path(self):
        """Verify that cache.get() with relative_path returns the cached structure (no 100% cache miss)."""
        cache = AstCache(str(self.cache_dir))
        struct = FileStructure(
            path=str(self.root / "src" / "api.py"),
            relative_path="src/api.py",
            language="Python",
            total_lines=50,
            classes=[CodeEntity(name="ApiServer", entity_type="class", signature="class ApiServer", line_number=10)],
            functions=[CodeEntity(name="start", entity_type="function", signature="def start()", line_number=20)],
            methods=[CodeEntity(name="ApiServer.handle", entity_type="method", signature="def handle(self)", line_number=15)]
        )
        mtime = 123456.0
        cache.put(struct, mtime, "sha_test")
        cache.commit()

        # Query using relative path - MUST HIT
        retrieved = cache.get("src/api.py", mtime)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.relative_path, "src/api.py")
        self.assertEqual(len(retrieved.methods), 1)
        self.assertEqual(retrieved.methods[0].name, "ApiServer.handle")

        # Query using absolute path - MUST ALSO HIT
        retrieved_abs = cache.get(str(self.root / "src" / "api.py"), mtime)
        self.assertIsNotNone(retrieved_abs)

        cache.close()

    def test_btree_symbol_search_and_speed(self):
        """Verify indexed symbol lookup accuracy and sub-millisecond retrieval speed."""
        cache = AstCache(str(self.cache_dir))

        # Insert 200 dummy symbols
        for i in range(200):
            s = FileStructure(
                path=f"/fake/module_{i}.py",
                relative_path=f"module_{i}.py",
                language="Python",
                total_lines=100,
                classes=[CodeEntity(name=f"Controller{i}", entity_type="class", signature=f"class Controller{i}", line_number=10)],
                functions=[CodeEntity(name=f"action_{i}", entity_type="function", signature=f"def action_{i}()", line_number=20)],
                methods=[CodeEntity(name=f"Controller{i}.execute", entity_type="method", signature="def execute(self)", line_number=30)]
            )
            cache.put(s, 1000.0 + i, f"sha_{i}")
        cache.commit()

        # Exact match test
        res_exact = cache.find_symbols("action_42", exact=True)
        self.assertEqual(len(res_exact), 1)
        self.assertEqual(res_exact[0]["name"], "action_42")
        self.assertEqual(res_exact[0]["entity_type"], "function")

        # Substring match test
        res_sub = cache.find_symbols("execute", exact=False, limit=10)
        self.assertEqual(len(res_sub), 10)
        self.assertEqual(res_sub[0]["simple_name"], "execute")

        # Type filter test
        res_methods = cache.find_symbols("Controller10", entity_type="class", exact=True)
        self.assertEqual(len(res_methods), 1)
        self.assertEqual(res_methods[0]["entity_type"], "class")

        # Benchmark exact B-Tree lookup speed: 100 queries
        start = time.perf_counter()
        iters = 100
        for _ in range(iters):
            _ = cache.find_symbols("action_42", exact=True)
        elapsed_sec = time.perf_counter() - start
        avg_ms_per_query = (elapsed_sec / iters) * 1000.0

        # Assert B-Tree speed is well under 1ms (<0.2ms typical on SQLite index)
        self.assertLess(avg_ms_per_query, 1.0, f"Average query took {avg_ms_per_query:.4f}ms, expected <1.0ms")

        cache.close()

    def test_mcp_find_symbols_tool(self):
        """Verify that cookiegli_find_symbols MCP tool executes cleanly and returns results."""
        py_file = self.root / "auth.py"
        py_file.write_text(
            "class AuthService:\n"
            "    def authenticate(self, token: str) -> bool:\n"
            "        return True\n",
            encoding="utf-8"
        )

        server = CookieGliMcpServer(workspace_root=self.root)
        tools = server.get_tools_manifest()
        tool_names = [t["name"] for t in tools]
        self.assertIn("cookiegli_find_symbols", tool_names)

        # Execute symbol search tool call
        rpc_req = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_find_symbols",
                "arguments": {
                    "query": "authenticate",
                    "exact": False,
                    "path": str(self.root)
                }
            }
        }
        resp = server.process_rpc_request(rpc_req)
        self.assertEqual(resp["id"], 10)
        content = resp["result"]["content"][0]["text"]
        self.assertIn("AuthService.authenticate", content)
        self.assertIn("method", content)

    def test_edge_cases_and_wildcard_escaping(self):
        """Verify wildcard characters %, _, \\ and empty queries are handled properly."""
        cache = AstCache(str(self.cache_dir))
        s = FileStructure(
            path=str(self.root / "wildcard.py"),
            relative_path="wildcard.py",
            language="Python",
            total_lines=10,
            classes=[],
            functions=[
                CodeEntity(name="calc_100%_func", entity_type="function", signature="def calc_100%_func()", line_number=1),
                CodeEntity(name="calc_other_func", entity_type="function", signature="def calc_other_func()", line_number=2),
            ]
        )
        cache.put(s, 100.0, "sha_wild")
        cache.commit()

        # Query searching for literal '100%' should NOT match calc_other_func
        res = cache.find_symbols("100%", exact=False)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["name"], "calc_100%_func")

        # Empty query returns all up to limit
        res_empty = cache.find_symbols("", limit=5)
        self.assertGreaterEqual(len(res_empty), 2)

        # Nonexistent entity type returns empty
        res_none = cache.find_symbols("calc", entity_type="nonexistent_type")
        self.assertEqual(len(res_none), 0)

        cache.close()

    def test_prune_missing_cleans_symbols(self):
        """Verify prune_missing cleans entries from both file_cache and symbol_cache."""
        cache = AstCache(str(self.cache_dir))
        s1 = FileStructure(
            path=str(self.root / "f1.py"),
            relative_path="f1.py",
            language="Python",
            total_lines=10,
            functions=[CodeEntity(name="active_sym", entity_type="function", signature="def active_sym()", line_number=1)]
        )
        s2 = FileStructure(
            path=str(self.root / "f2.py"),
            relative_path="f2.py",
            language="Python",
            total_lines=10,
            functions=[CodeEntity(name="deleted_sym", entity_type="function", signature="def deleted_sym()", line_number=1)]
        )
        cache.put(s1, 100.0, "sha1")
        cache.put(s2, 100.0, "sha2")
        cache.commit()

        self.assertEqual(len(cache.find_symbols("deleted_sym")), 1)

        # Prune f2.py by only keeping f1.py
        pruned = cache.prune_missing(["f1.py"])
        self.assertEqual(pruned, 1)

        # deleted_sym must be gone from symbol_cache
        self.assertEqual(len(cache.find_symbols("deleted_sym")), 0)
        self.assertEqual(len(cache.find_symbols("active_sym")), 1)

        cache.close()

    def test_windows_backslash_cache_hit(self):
        """Verify that cache.get() with Windows backslashes hits the cache."""
        cache = AstCache(str(self.cache_dir))
        struct = FileStructure(
            path=str(self.root / "src" / "service.py"),
            relative_path="src/service.py",
            language="Python",
            total_lines=25,
            classes=[CodeEntity(name="Service", entity_type="class", signature="class Service", line_number=5)]
        )
        mtime = 54321.0
        cache.put(struct, mtime, "sha_win")
        cache.commit()

        # Query using Windows backslash relative path
        retrieved_backslash = cache.get("src\\service.py", mtime)
        self.assertIsNotNone(retrieved_backslash)
        self.assertEqual(retrieved_backslash.classes[0].name, "Service")

        cache.close()

    def test_monorepo_inter_package_deps_resolution(self):
        """Verify that monorepo engine accurately resolves internal package dependencies from both internal and scoped imports."""
        pkg1 = self.root / "packages" / "auth_service"
        pkg1.mkdir(parents=True)
        (pkg1 / "pyproject.toml").write_text("[project]\nname='auth_service'", encoding='utf-8')
        (pkg1 / "auth.py").write_text("class AuthService:\n    pass\n", encoding='utf-8')

        pkg2 = self.root / "packages" / "web_dashboard"
        pkg2.mkdir(parents=True)
        (pkg2 / "pyproject.toml").write_text("[project]\nname='web_dashboard'", encoding='utf-8')
        (pkg2 / "main.py").write_text("from auth_service.auth import AuthService\n", encoding='utf-8')

        engine = MonorepoEngine(str(self.root), use_cache=False)
        genome = engine.build()

        self.assertIn("auth_service", genome.packages["web_dashboard"].internal_deps)
        self.assertIn("web_dashboard", genome.inter_package_graph)
        self.assertIn("auth_service", genome.inter_package_graph["web_dashboard"])

    def test_generics_and_constructor_method_extraction(self):
        """Verify Go generic receivers, TypeScript generic methods, and Java constructors."""
        go_code = (
            "package main\n\n"
            "type Container[T any] struct {}\n\n"
            "func (c *Container[T]) Store(val T) bool {\n"
            "    return true\n"
            "}\n"
        )
        (self.root / "generic.go").write_text(go_code, encoding="utf-8")

        ts_code = (
            "export class DataStore<T> {\n"
            "    public async fetchRecord<R>(id: string): Promise<R> {\n"
            "        return {} as R;\n"
            "    }\n"
            "}\n"
        )
        (self.root / "generic.ts").write_text(ts_code, encoding="utf-8")

        java_code = (
            "public class AccountManager {\n"
            "    public AccountManager(String username) {\n"
            "    }\n"
            "    public <T> T query(String sql) {\n"
            "        return null;\n"
            "    }\n"
            "}\n"
        )
        (self.root / "AccountManager.java").write_text(java_code, encoding="utf-8")

        with AstScanner(str(self.root), use_cache=False) as scanner:
            results = scanner.scan()

        go_struct = next(r for r in results if r.relative_path == "generic.go")
        go_methods = [m.name for m in go_struct.methods]
        self.assertIn("Container.Store", go_methods)

        ts_struct = next(r for r in results if r.relative_path == "generic.ts")
        ts_methods = [m.name for m in ts_struct.methods]
        self.assertIn("DataStore.fetchRecord", ts_methods)

        java_struct = next(r for r in results if r.relative_path == "AccountManager.java")
        java_methods = [m.name for m in java_struct.methods]
        self.assertIn("AccountManager.AccountManager", java_methods)
        self.assertIn("AccountManager.query", java_methods)

    def test_symbol_cache_filepath_index_and_explain(self):
        """Verify idx_sym_filepath exists and delete query uses MULTI-INDEX OR without full table scan."""
        with AstCache(str(self.cache_dir)) as cache:
            cur = cache.conn.cursor()
            cur.execute("EXPLAIN QUERY PLAN DELETE FROM symbol_cache WHERE file_path = ? OR relative_path = ?", ("/tmp/f.py", "f.py"))
            plan = [dict(r)["detail"] for r in cur.fetchall()]
            plan_str = " ".join(plan)
            self.assertIn("MULTI-INDEX OR", plan_str)
            self.assertNotIn("SCAN symbol_cache", plan_str)

    def test_mcp_find_symbols_with_relative_file_filter(self):
        """Verify MCP find symbols works with relative file paths and releases file locks."""
        py_file = self.root / "user_service.py"
        py_file.write_text("class UserService:\n    def find_user(self, uid: int): pass\n", encoding="utf-8")

        with CookieGliMcpServer(workspace_root=self.root) as server:
            resp = server.handle_tool_call(
                "cookiegli_find_symbols",
                {"query": "find_user", "path": "user_service.py"}
            )
            self.assertIn("UserService.find_user", resp)
            self.assertIn("user_service.py", resp)

    def test_fts5_virtual_table_and_bm25_ranking(self):
        """Verify SQLite FTS5 BM25+ search ranking and trigger sync."""
        py_file = self.root / "billing_service.py"
        py_file.write_text(
            "class BillingManager:\n"
            "    \"\"\"Manages subscription payments.\"\"\"\n"
            "    def process_payment(self, amount: float, token: str) -> bool:\n"
            "        \"\"\"Process credit card charge.\"\"\"\n"
            "        return True\n"
            "\n"
            "    def refund_transaction(self, tx_id: str) -> bool:\n"
            "        \"\"\"Refund previous transaction.\"\"\"\n"
            "        return True\n",
            encoding="utf-8"
        )

        with AstScanner(str(self.root), use_cache=True, cache_dir=str(self.cache_dir)) as scanner:
            scanner.scan()

        with AstCache(str(self.cache_dir)) as cache:
            # Check virtual table exists
            cur = cache.conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='symbol_fts'")
            tbl = cur.fetchone()
            if not tbl:
                self.skipTest("FTS5 module not available in this SQLite build")

            # Check 3 triggers exist
            cur.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'trig_symbol_cache_%'")
            triggers = {r["name"] for r in cur.fetchall()}
            self.assertIn("trig_symbol_cache_ai", triggers)
            self.assertIn("trig_symbol_cache_ad", triggers)
            self.assertIn("trig_symbol_cache_au", triggers)

            # Search by function docstring / term
            results = cache.search_bm25("process payment credit card charge")
            self.assertGreater(len(results), 0)
            self.assertEqual(results[0]["name"], "BillingManager.process_payment")
            self.assertIn("score", results[0])

            # Search by refund
            refund_res = cache.search_bm25("refund transaction")
            self.assertGreater(len(refund_res), 0)
            self.assertEqual(refund_res[0]["name"], "BillingManager.refund_transaction")

    def test_fts5_trigger_delete_and_clear_sync(self):
        """Verify that FTS5 table is automatically synced on deletion and clearing."""
        py_file = self.root / "auth.py"
        py_file.write_text("class AuthValidator:\n    def validate_hash(self, h: str): pass\n", encoding="utf-8")

        with AstScanner(str(self.root), use_cache=True, cache_dir=str(self.cache_dir)) as scanner:
            scanner.scan()

        with AstCache(str(self.cache_dir)) as cache:
            if not getattr(cache, 'fts5_available', False):
                self.skipTest("FTS5 not available")

            # Must find AuthValidator
            hits = cache.search_bm25("AuthValidator")
            self.assertGreater(len(hits), 0)

            # Clear cache
            cache.clear()

            # Must be empty in both B-Tree and FTS
            hits_after = cache.search_bm25("AuthValidator")
            self.assertEqual(len(hits_after), 0)


    def test_fts5_disabled_fallback_to_btree(self):
        """Verify that when FTS5 is disabled, search_bm25 falls back gracefully to indexed B-tree search."""
        py_file = self.root / "payment.py"
        py_file.write_text("class PaymentProcessor:\n    def process_charge(self, amount: int): pass\n", encoding="utf-8")

        with AstScanner(str(self.root), use_cache=True, cache_dir=str(self.cache_dir)) as scanner:
            scanner.scan()

        with AstCache(str(self.cache_dir)) as cache:
            # Force FTS5 unavailable to simulate environments without FTS5 compile flags
            cache.fts5_available = False

            results = cache.search_bm25("PaymentProcessor")
            self.assertGreater(len(results), 0)
            self.assertEqual(results[0]["name"], "PaymentProcessor")
            self.assertEqual(results[0]["entity_type"], "class")

            # Search method
            method_hits = cache.search_bm25("process_charge")
            self.assertGreater(len(method_hits), 0)
            self.assertIn("PaymentProcessor.process_charge", [m["name"] for m in method_hits])

    def test_bm25_deduplication_and_punctuation_handling(self):
        """Verify duplicate search tokens, punctuation, and single-character tokens work cleanly."""
        py_file = self.root / "search_target.py"
        py_file.write_text("class TargetService:\n    def execute(self, a: int): pass\n", encoding="utf-8")

        with AstScanner(str(self.root), use_cache=True, cache_dir=str(self.cache_dir)) as scanner:
            scanner.scan()

        with AstCache(str(self.cache_dir)) as cache:
            # Query with duplicate words, punctuation, and 1-char tokens
            res = cache.search_bm25("TargetService in a in service! (execute?)")
            self.assertGreater(len(res), 0)
            self.assertIn("TargetService", [r["name"] for r in res])

            # Query with exclusively punctuation
            empty_res = cache.search_bm25("!@#$%^&*()")
            self.assertEqual(len(empty_res), 0)


if __name__ == '__main__':
    unittest.main()

