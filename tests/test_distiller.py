"""
Unit tests for CookieGli Autonomous Error & Traceback Distiller (Step 4).
Covers 3-tier parser dispatch, runner frame filtering, diff pattern synthesis,
Laplace Bayesian priors, deduplication & pruned resurrection, clean sync, and MCP/CLI.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))
sys.path.insert(0, str(REPO_ROOT))

from cookiegli_core.distiller import (
    ErrorDistiller,
    DistilledError,
    DistilledLesson,
    StackFrame,
    clean_darwin_summary,
    resolve_darwin_state_path,
)
from cookiegli_core.darwin_memory import DarwinMemory
from cookiegli_core.mcp_server import CookieGliMcpServer
import cli.cookiegli as cli_module


class TestDistiller(unittest.TestCase):
    """22 comprehensive unit tests for Error & Traceback Distiller."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name).resolve()
        self.distiller = ErrorDistiller(workspace_root=self.workspace_root)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # 1. Python standard traceback
    def test_python_standard_traceback(self):
        log = """
Traceback (most recent call last):
  File "src/server.py", line 45, in handle_request
    response = router.dispatch(req)
  File "src/router.py", line 112, in dispatch
    return handler(req)
  File "src/handlers/user.py", line 28, in get_user
    user_id = int(req.params["id"])
ValueError: invalid literal for int() with base 10: 'abc'
"""
        err = self.distiller.parse_error(log)
        self.assertEqual(err.runner, "python")
        self.assertEqual(err.error_type, "ValueError")
        self.assertEqual(err.error_message, "invalid literal for int() with base 10: 'abc'")
        self.assertEqual(len(err.frames), 3)
        self.assertIsNotNone(err.root_cause_frame)
        self.assertEqual(err.root_cause_frame.file, "src/handlers/user.py")
        self.assertEqual(err.root_cause_frame.line, 28)
        self.assertEqual(err.root_cause_frame.function, "get_user")
        self.assertEqual(err.root_cause_frame.code, 'user_id = int(req.params["id"])')

    # 2. Syntax and indentation error
    def test_syntax_and_indentation_error(self):
        syntax_log = """
  File "src/parser.py", line 42
    def process_data(data)
                          ^
SyntaxError: expected ':'
"""
        err = self.distiller.parse_error(syntax_log)
        self.assertEqual(err.error_type, "SyntaxError")
        self.assertEqual(err.error_message, "expected ':'")
        self.assertIsNotNone(err.root_cause_frame)
        self.assertEqual(err.root_cause_frame.file, "src/parser.py")
        self.assertEqual(err.root_cause_frame.line, 42)

        indent_log = """
  File "src/service.py", line 80
    result = compute()
IndentationError: unexpected indent
"""
        err2 = self.distiller.parse_error(indent_log)
        self.assertEqual(err2.error_type, "IndentationError")
        self.assertEqual(err2.error_message, "unexpected indent")
        self.assertEqual(err2.root_cause_frame.file, "src/service.py")
        self.assertEqual(err2.root_cause_frame.line, 80)

    # 3. Chained exceptions
    def test_chained_exceptions(self):
        chained_log = """
Traceback (most recent call last):
  File "src/db.py", line 15, in connect
    raise ConnectionRefusedError("connection failed")
ConnectionRefusedError: connection failed

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "src/app.py", line 60, in start
    self.init_db()
  File "src/app.py", line 30, in init_db
    raise RuntimeError("Failed to initialize database")
RuntimeError: Failed to initialize database
"""
        err = self.distiller.parse_error(chained_log)
        self.assertEqual(err.error_type, "RuntimeError")
        self.assertEqual(err.error_message, "Failed to initialize database")
        self.assertEqual(len(err.chained_errors), 1)
        prev = err.chained_errors[0]
        self.assertEqual(prev.error_type, "ConnectionRefusedError")
        self.assertEqual(prev.error_message, "connection failed")
        self.assertEqual(prev.root_cause_frame.file, "src/db.py")

    # 4. Unittest runner parsing
    def test_unittest_runner_parsing(self):
        unittest_log = """
======================================================================
FAIL: test_calculate_metrics (tests.test_metrics.TestMetrics.test_calculate_metrics)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "tests/test_metrics.py", line 55, in test_calculate_metrics
    self.assertEqual(result, 100)
AssertionError: 95 != 100

----------------------------------------------------------------------
Ran 5 tests in 0.045s

FAILED (failures=1)
"""
        err = self.distiller.parse_error(unittest_log)
        self.assertEqual(err.runner, "unittest")
        self.assertEqual(err.error_type, "AssertionError")
        self.assertEqual(err.error_message, "95 != 100")
        self.assertIsNotNone(err.root_cause_frame)
        self.assertEqual(err.root_cause_frame.file, "tests/test_metrics.py")
        self.assertEqual(err.root_cause_frame.line, 55)

    # 5. Pytest runner parsing
    def test_pytest_runner_parsing(self):
        pytest_log = """
============================= test session starts =============================
collected 3 items

tests/test_calc.py .F.                                                  [100%]

================================== FAILURES ===================================
_________________________________ test_divide _________________________________

    def test_divide():
>       assert divide(10, 0) == 0

src/calculator.py:12: in divide
    return a / b
E   ZeroDivisionError: division by zero

tests/test_calc.py:20: ZeroDivisionError
=========================== short test summary info ===========================
FAILED tests/test_calc.py::test_divide - ZeroDivisionError: division by zero
========================= 1 failed, 2 passed in 0.08s =========================
"""
        err = self.distiller.parse_error(pytest_log)
        self.assertEqual(err.runner, "pytest")
        self.assertEqual(err.error_type, "ZeroDivisionError")
        self.assertEqual(err.error_message, "division by zero")
        self.assertIsNotNone(err.root_cause_frame)
        # Deepest project frame is src/calculator.py:12
        self.assertIn("calculator.py", err.root_cause_frame.file)

    # 6. Jest runner parsing
    def test_jest_runner_parsing(self):
        jest_log = """
FAIL src/services/auth.test.ts
  ● AuthService › should validate token

    expect(received).toBe(expected) // Object.is equality

    Expected: true
    Received: false

      24 |     const isValid = service.validate(token);
    > 25 |     expect(isValid).toBe(true);
         |                     ^
      26 |   });

      at Object.<anonymous> (src/services/auth.test.ts:25:21)
      at Promise.then.completed (node_modules/jest-circus/build/utils.js:333:28)
"""
        err = self.distiller.parse_error(jest_log)
        self.assertEqual(err.runner, "jest")
        self.assertEqual(err.error_type, "AssertionError")
        self.assertIn("Expected: true, Received: false", err.error_message)
        self.assertIsNotNone(err.root_cause_frame)
        self.assertEqual(err.root_cause_frame.file, "src/services/auth.test.ts")
        self.assertEqual(err.root_cause_frame.line, 25)

    # 7. Node.js stack trace
    def test_node_stack_parsing(self):
        node_log = """
TypeError: Cannot read properties of undefined (reading 'username')
    at getUserProfile (/app/src/controllers/user.js:42:25)
    at Layer.handle [as handle_request] (/app/node_modules/express/lib/router/layer.js:95:5)
    at next (/app/node_modules/express/lib/router/route.js:144:13)
"""
        err = self.distiller.parse_error(node_log)
        self.assertEqual(err.runner, "node")
        self.assertEqual(err.error_type, "TypeError")
        self.assertEqual(err.error_message, "Cannot read properties of undefined (reading 'username')")
        self.assertIsNotNone(err.root_cause_frame)
        self.assertIn("controllers/user.js", err.root_cause_frame.file)
        self.assertEqual(err.root_cause_frame.line, 42)

    # 8. Go panic and test
    def test_go_panic_and_test(self):
        go_panic_log = """
panic: runtime error: index out of range [5] with length 3

goroutine 1 [running]:
main.getElement(0x1, 0x2)
\t/home/user/project/src/worker.go:28 +0x39
main.main()
\t/home/user/project/src/main.go:15 +0x45
"""
        err = self.distiller.parse_error(go_panic_log)
        self.assertEqual(err.runner, "go")
        self.assertEqual(err.error_type, "IndexOutOfRange")
        self.assertIn("index out of range", err.error_message)
        self.assertIsNotNone(err.root_cause_frame)
        self.assertIn("src/main.go", err.root_cause_frame.file)

        go_test_log = """
=== RUN   TestProcessQueue
--- FAIL: TestProcessQueue (0.02s)
    queue_test.go:48: queue did not drain: remaining 4 items
FAIL
"""
        err2 = self.distiller.parse_error(go_test_log)
        self.assertEqual(err2.runner, "go_test")
        self.assertEqual(err2.error_type, "TestFailure")
        self.assertIn("queue did not drain", err2.error_message)
        self.assertIsNotNone(err2.root_cause_frame)
        self.assertEqual(err2.root_cause_frame.file, "queue_test.go")
        self.assertEqual(err2.root_cause_frame.line, 48)

    # 9. Rust panic
    def test_rust_panic(self):
        rust_log = """
thread 'main' panicked at 'called `Option::unwrap()` on a `None` value', src/storage/db.rs:65:21
stack backtrace:
   0: rust_begin_unwind
             at /rustc/library/std/src/panicking.rs:593:5
   1: core::panicking::panic_fmt
             at /rustc/library/core/src/panicking.rs:67:14
   2: my_crate::storage::db::get_connection
             at src/storage/db.rs:65:21
"""
        err = self.distiller.parse_error(rust_log)
        self.assertEqual(err.runner, "rust")
        self.assertEqual(err.error_type, "UnwrapNone")
        self.assertIn("called `Option::unwrap()` on a `None` value", err.error_message)
        self.assertIsNotNone(err.root_cause_frame)
        self.assertEqual(err.root_cause_frame.file, "src/storage/db.rs")
        self.assertEqual(err.root_cause_frame.line, 65)

    # 10. ANSI stripping and window limiting
    def test_ansi_stripping_and_window_limiting(self):
        ansi_text = "\x1b[31;1mError:\x1b[0m \x1b[33mSomething failed\x1b[0m\r\nLine 2\r\n"
        cleaned = self.distiller.clean_log(ansi_text)
        self.assertEqual(cleaned, "Error: Something failed\nLine 2\n")

        # Huge log exceeding 3000 lines
        huge_log = "\n".join([f"line_{i}" for i in range(5000)])
        windowed = self.distiller.clean_log(huge_log)
        lines = windowed.split('\n')
        self.assertEqual(len(lines), 3000)
        self.assertEqual(lines[0], "line_2000")
        self.assertEqual(lines[-1], "line_4999")

    # 11. Path normalization
    def test_path_normalization(self):
        # Quotes and backslashes
        norm1 = self.distiller.normalize_path('"C:\\project\\src\\utils\\helper.py"')
        self.assertTrue(norm1.endswith("src/utils/helper.py") or "src/utils/helper.py" in norm1)
        self.assertNotIn("\\", norm1)
        self.assertNotIn('"', norm1)

        # Leading ./
        norm2 = self.distiller.normalize_path('./src/module.py')
        self.assertEqual(norm2, "src/module.py")

        # Absolute inside workspace root
        target_file = self.workspace_root / "src" / "index.py"
        norm3 = self.distiller.normalize_path(str(target_file))
        self.assertEqual(norm3, "src/index.py")

    # 12. Runner frame filtering
    def test_runner_frame_filtering(self):
        self.assertFalse(self.distiller.classify_frame("site-packages/pytest/runner.py"))
        self.assertFalse(self.distiller.classify_frame("C:/Python310/Lib/unittest/case.py"))
        self.assertFalse(self.distiller.classify_frame("node_modules/express/index.js"))
        self.assertFalse(self.distiller.classify_frame("<frozen importlib._bootstrap>"))
        self.assertFalse(self.distiller.classify_frame("/rustc/library/std/src/panicking.rs"))

        self.assertTrue(self.distiller.classify_frame("src/cookiegli_core/cache_db.py"))
        self.assertTrue(self.distiller.classify_frame("tests/test_cache_db.py"))
        self.assertTrue(self.distiller.classify_frame("app/services/user_service.ts"))

    # 13. Domain heuristics
    def test_domain_scope_heuristics(self):
        err_cache = DistilledError("KeyError", "missing cache key", "python", StackFrame("src/cookiegli_core/cache_db.py", 10, "get"))
        self.assertEqual(self.distiller.infer_domain_scope(err_cache), "core.cache")

        err_sqlite = DistilledError("DatabaseError", "sqlite wal lock busy", "python", StackFrame("src/db/sqlite_pool.py", 15, "exec"))
        self.assertEqual(self.distiller.infer_domain_scope(err_sqlite), "storage.sqlite")

        err_ast = DistilledError("SyntaxError", "ast folding unparse error", "python", StackFrame("src/cookiegli_core/skeletonizer.py", 50, "skeletonize"))
        self.assertEqual(self.distiller.infer_domain_scope(err_ast), "engine.ast")

        err_blast = DistilledError("RuntimeError", "graph ingress dependency traversal cycle", "python", StackFrame("src/cookiegli_core/blast_radius.py", 30, "analyze"))
        self.assertEqual(self.distiller.infer_domain_scope(err_blast), "git.blast")

        err_mcp = DistilledError("ValueError", "unknown tool cookiegli_mcp json-rpc", "python", StackFrame("src/cookiegli_core/mcp_server.py", 40, "handle"))
        self.assertEqual(self.distiller.infer_domain_scope(err_mcp), "mcp.tools")

        err_auth = DistilledError("AuthError", "jwt token expired", "python", StackFrame("src/auth/jwt_handler.py", 20, "verify"))
        self.assertEqual(self.distiller.infer_domain_scope(err_auth), "backend.auth")

    # 14. Diff pattern synthesis - Null Guard
    def test_diff_pattern_synthesis_null_guard(self):
        err = DistilledError("TypeError", "'NoneType' object has no attribute 'token'", "python", StackFrame("src/auth/user.py", 22, "login"))
        diff = """
--- a/src/auth/user.py
+++ b/src/auth/user.py
@@ -20,3 +20,4 @@
+    if user is not None:
+        token = user.token
"""
        lesson = self.distiller.synthesize_lesson(err, diff_text=diff)
        self.assertIn("Null Guard", lesson.name)
        self.assertIn("Validate object existence with explicit null/None check", lesson.content)
        self.assertIn("null-safety", lesson.tags)
        self.assertAlmostEqual(lesson.roi, 0.53, places=2)
        self.assertAlmostEqual(lesson.success_rate, 0.67, places=2)

    # 15. Diff pattern synthesis - Default Fallback
    def test_diff_pattern_synthesis_default_fallback(self):
        err = DistilledError("KeyError", "'session_id'", "python", StackFrame("src/session/manager.py", 40, "get_session"))
        diff = """
--- a/src/session/manager.py
+++ b/src/session/manager.py
@@ -38,3 +38,3 @@
-    val = data['session_id']
+    val = data.get('session_id', '')
"""
        lesson = self.distiller.synthesize_lesson(err, diff_text=diff)
        self.assertIn("Default Fallback", lesson.name)
        self.assertIn(".get()", lesson.content)
        self.assertIn("fallback", lesson.tags)

    # 16. Diff pattern synthesis - Bounds Check
    def test_diff_pattern_synthesis_bounds_check(self):
        err = DistilledError("IndexError", "list index out of range", "python", StackFrame("src/queue/worker.py", 15, "pop_next"))
        diff = """
--- a/src/queue/worker.py
+++ b/src/queue/worker.py
@@ -14,3 +14,3 @@
-    return items[idx]
+    if idx < len(items):
+        return items[idx]
"""
        lesson = self.distiller.synthesize_lesson(err, diff_text=diff)
        self.assertIn("Bounds Guard", lesson.name)
        self.assertIn("Verify index bounds against collection length", lesson.content)

    # 17. Diff pattern synthesis - ast.Pass() / Empty block guard
    def test_diff_pattern_synthesis_ast_pass(self):
        err = DistilledError("IndentationError", "expected an indented block after class definition", "python", StackFrame("src/engine/ast_builder.py", 88, "build"))
        diff = """
--- a/src/engine/ast_builder.py
+++ b/src/engine/ast_builder.py
@@ -87,3 +87,4 @@
+    if not class_body:
+        class_body.append(ast.Pass())
"""
        lesson = self.distiller.synthesize_lesson(err, diff_text=diff)
        self.assertIn("Empty Block Invariant", lesson.name)
        self.assertIn("ast.Pass()", lesson.content)

    # 18. Diff pattern synthesis - Path Normalization
    def test_diff_pattern_synthesis_path_norm(self):
        err = DistilledError("FileNotFoundError", "No such file or directory: 'C:\\\\dir\\\\file.txt'", "python", StackFrame("src/io/loader.py", 19, "load"))
        diff = """
--- a/src/io/loader.py
+++ b/src/io/loader.py
@@ -18,3 +18,3 @@
-    clean_path = raw_path
+    clean_path = raw_path.replace('\\', '/')
"""
        lesson = self.distiller.synthesize_lesson(err, diff_text=diff)
        self.assertIn("Path Normalization", lesson.name)
        self.assertIn("forward slashes", lesson.content)

    # 19. Fix description synthesis
    def test_fix_description_synthesis(self):
        err = DistilledError("ValueError", "invalid uuid string format", "python", StackFrame("src/models/user.py", 14, "from_uuid"))
        lesson = self.distiller.synthesize_lesson(err, fix_description="Add regex validation before uuid parsing")
        self.assertIn("User Fix: Add regex validation", lesson.name)
        self.assertIn("Prevent ValueError in src/models/user.py: Add regex validation before uuid parsing", lesson.content)

    # 20. Pure traceback fallback
    def test_pure_traceback_fallback(self):
        err = DistilledError("ZeroDivisionError", "division by zero", "python", StackFrame("src/math/calc.py", 8, "divide"))
        lesson = self.distiller.synthesize_lesson(err)
        self.assertIn("Non-Zero Divisor Guard", lesson.name)
        self.assertIn("Validate divisor is non-zero before performing division", lesson.content)

        err_key = DistilledError("KeyError", "'api_key'", "python", StackFrame("src/config.py", 33, "load"))
        lesson_key = self.distiller.synthesize_lesson(err_key)
        self.assertIn("Safe Key Lookup", lesson_key.name)
        self.assertIn("api_key", lesson_key.content)

    # 21. Auto-registration, deduplication, and pruned resurrection
    def test_auto_registration_and_pruned_resurrection(self):
        state_file = self.workspace_root / ".cookiegli" / "darwin_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        memory = DarwinMemory(state_file=str(state_file))

        distiller = ErrorDistiller(workspace_root=self.workspace_root, memory=memory)
        lesson = DistilledLesson(
            name="Null Guard in AuthService",
            artifact_type="lesson",
            content="Check for null token before validation",
            scope="backend.auth"
        )

        # 1. Register new artifact
        art1 = distiller.register_lesson(lesson)
        self.assertIsNotNone(art1)
        self.assertEqual(art1.name, "Null Guard in AuthService")
        self.assertEqual(art1.use_count, 1)
        self.assertEqual(art1.success_count, 1)
        self.assertAlmostEqual(art1.roi, 0.53, places=2)
        self.assertFalse(art1.pruned)

        # 2. Prune artifact
        art1.pruned = True
        art1.prune_reason = "Capacity constraint"
        memory.save()
        self.assertTrue(memory.artifacts[art1.id].pruned)

        # 3. Resurrect via deduplication + registration
        updated_lesson = DistilledLesson(
            name="Null Guard in AuthService",
            artifact_type="lesson",
            content="Check for null token and empty string before validation",
            scope="backend.auth"
        )
        art2 = distiller.register_lesson(updated_lesson)
        self.assertEqual(art1.id, art2.id)
        self.assertFalse(art2.pruned)
        self.assertEqual(art2.prune_reason, "")
        self.assertEqual(art2.use_count, 2)
        self.assertEqual(art2.success_count, 2)
        self.assertEqual(art2.content, "Check for null token and empty string before validation")

    # 22. Clean sync and MCP / CLI
    def test_clean_sync_and_mcp_cli(self):
        # Test clean_darwin_summary
        dirty_summary = """<!-- darwin:learnings:start -->
### 🧬 Darwin Learned Patterns & Best Practices
- [LESSON] **Windows Shell Safety** `[core]` (ROI: 1.00, SR: 100%): Pure python.
<!-- darwin:learnings:end -->"""
        cleaned = clean_darwin_summary(dirty_summary)
        self.assertNotIn("<!-- darwin:learnings:start -->", cleaned)
        self.assertNotIn("<!-- darwin:learnings:end -->", cleaned)
        self.assertNotIn("### 🧬", cleaned)
        self.assertEqual(cleaned, "- [LESSON] **Windows Shell Safety** `[core]` (ROI: 1.00, SR: 100%): Pure python.")

        # Test resolve_darwin_state_path priority
        p1 = self.workspace_root / ".cookiegli" / "darwin_state.json"
        p2 = self.workspace_root / ".agents" / ".darwin_state.json"

        # Initially neither exists -> defaults to p1
        self.assertEqual(resolve_darwin_state_path(self.workspace_root), p1)

        # When only p2 exists -> returns p2
        p2.parent.mkdir(parents=True, exist_ok=True)
        p2.write_text("{}", encoding='utf-8')
        self.assertEqual(resolve_darwin_state_path(self.workspace_root), p2)

        # When p1 also exists -> p1 takes priority
        p1.parent.mkdir(parents=True, exist_ok=True)
        p1.write_text("{}", encoding='utf-8')
        self.assertEqual(resolve_darwin_state_path(self.workspace_root), p1)

        # Test MCP Server cookiegli_distill_lesson
        with CookieGliMcpServer(workspace_root=self.workspace_root) as server:
            tb = """Traceback (most recent call last):
  File "src/service.py", line 10, in execute
    return 10 / 0
ZeroDivisionError: division by zero"""
            resp_str = server.handle_tool_call("cookiegli_distill_lesson", {
                "traceback": tb,
                "diff": "+++ b/src/service.py\n+    if divisor != 0:\n+        return 10 / divisor",
                "auto_register": True
            })
            resp = json.loads(resp_str)
            self.assertEqual(resp["error"]["type"], "ZeroDivisionError")
            self.assertIn("lesson", resp)
            self.assertIsNotNone(resp["registered"])

        # Test CLI cmd_distill via namespace
        import argparse
        import io
        from unittest.mock import patch
        args = argparse.Namespace(
            root=str(self.workspace_root),
            state=None,
            traceback=tb,
            file=None,
            diff=None,
            diff_file=None,
            fix="Explicit non-zero check",
            auto_register=True,
            sync=None,
            scope="core.math",
            json=True
        )
        with patch('sys.stdout', new_callable=io.StringIO):
            code = cli_module.cmd_distill(args)
        self.assertEqual(code, 0)

    # 23. Python traceback without code line & adjacent frames
    def test_traceback_without_code_lines(self):
        log = """Traceback (most recent call last):
  File "src/runner.py", line 15, in run
  File "src/worker.py", line 42, in execute
    result = compute()
  File "src/math_util.py", line 100, in compute
ZeroDivisionError: division by zero"""
        err = self.distiller.parse_error(log)
        self.assertEqual(len(err.frames), 3)
        self.assertEqual(err.frames[0].file, "src/runner.py")
        self.assertEqual(err.frames[0].code, "")
        self.assertEqual(err.frames[1].file, "src/worker.py")
        self.assertEqual(err.frames[1].code, "result = compute()")
        self.assertEqual(err.frames[2].file, "src/math_util.py")
        self.assertEqual(err.frames[2].code, "")
        self.assertEqual(err.root_cause_frame.file, "src/math_util.py")

    # 24. Windows absolute path parsing across runners
    def test_windows_absolute_paths_across_runners(self):
        # Jest
        jest_win = """FAIL C:/project/src/auth.test.ts
  ● Auth › test
    expect(received).toBe(expected)
    Expected: 1
    Received: 2
      at Object.<anonymous> (C:\\project\\src\\auth.test.ts:30:15)
"""
        err_jest = self.distiller.parse_error(jest_win)
        self.assertEqual(err_jest.runner, "jest")
        self.assertIsNotNone(err_jest.root_cause_frame)
        self.assertEqual(err_jest.root_cause_frame.line, 30)

        # Node
        node_win = """Error: Crash
    at run (D:\\app\\src\\index.js:55:10)
"""
        err_node = self.distiller.parse_error(node_win)
        self.assertEqual(err_node.runner, "node")
        self.assertIsNotNone(err_node.root_cause_frame)
        self.assertEqual(err_node.root_cause_frame.line, 55)

        # Go panic
        go_win = """panic: runtime error: index out of range [2] with length 1
goroutine 1 [running]:
main.doWork(0x1)
\tC:/GoProjects/src/worker.go:88 +0x20"""
        err_go = self.distiller.parse_error(go_win)
        self.assertEqual(err_go.runner, "go")
        self.assertIsNotNone(err_go.root_cause_frame)
        self.assertEqual(err_go.root_cause_frame.line, 88)

        # Go test
        go_test_win = """--- FAIL: TestWin (0.01s)
    C:\\GoProjects\\worker_test.go:44: assertion failed
FAIL"""
        err_gotest = self.distiller.parse_error(go_test_win)
        self.assertEqual(err_gotest.runner, "go_test")
        self.assertIsNotNone(err_gotest.root_cause_frame)
        self.assertEqual(err_gotest.root_cause_frame.line, 44)

        # Rust panic
        rust_win = "thread 'main' panicked at 'assertion failed', C:\\rust\\src\\lib.rs:99:5"
        err_rust = self.distiller.parse_error(rust_win)
        self.assertEqual(err_rust.runner, "rust")
        self.assertIsNotNone(err_rust.root_cause_frame)
        self.assertEqual(err_rust.root_cause_frame.line, 99)

        # Generic
        gen_win = "FATAL: error in C:\\project\\src\\server.py:120"
        err_gen = self.distiller.parse_error(gen_win)
        self.assertIsNotNone(err_gen.root_cause_frame)
        self.assertEqual(err_gen.root_cause_frame.line, 120)

    # 25. Windows Python stdlib path classification
    def test_windows_python_stdlib_frame_filtering(self):
        # Frame from Windows python stdlib
        win_stdlib = r"C:\Users\User\AppData\Local\Programs\Python\Python311\Lib\json\decoder.py"
        self.assertFalse(self.distiller.classify_frame(win_stdlib))

        # Project file that happens to be named lib/something.py
        proj_lib = "src/lib/parser.py"
        self.assertTrue(self.distiller.classify_frame(proj_lib))

        # Traceback passing through stdlib
        tb = f"""Traceback (most recent call last):
  File "src/main.py", line 20, in run
    json.loads("bad")
  File "{win_stdlib}", line 353, in raw_decode
    obj, end = self.raw_decode(s, idx=_w(s, 0).end())
json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)"""
        err = self.distiller.parse_error(tb)
        # Root cause should be the project frame, not stdlib
        self.assertIsNotNone(err.root_cause_frame)
        self.assertEqual(err.root_cause_frame.file, "src/main.py")

    # 26. Safe inject_bounded_block protecting documentation examples
    def test_safe_inject_bounded_block(self):
        from cookiegli_core.adapters import TargetManager
        doc = """# Instructions
Here is how to structure it:
```markdown
  <!-- darwin:learnings:start -->
  ### 🧬 Darwin Learned Patterns & Best Practices
  - [EXAMPLE] Rule
  <!-- darwin:learnings:end -->
```

<!-- darwin:learnings:start -->
### 🧬 Darwin Learned Patterns & Best Practices
- [OLD] Old pattern
<!-- darwin:learnings:end -->
"""
        updated = TargetManager._inject_bounded_block(
            doc,
            "<!-- darwin:learnings:start -->",
            "<!-- darwin:learnings:end -->",
            "### 🧬 Darwin Learned Patterns & Best Practices\n- [NEW] New pattern"
        )
        # Example in code fence remains untouched
        self.assertIn("- [EXAMPLE] Rule", updated)
        # Operational block updated
        self.assertIn("- [NEW] New pattern", updated)
        self.assertNotIn("- [OLD] Old pattern", updated)

    # 27. Distill with scope override
    def test_distill_scope_override(self):
        tb = """Traceback (most recent call last):
  File "src/api.py", line 10, in call
    raise ValueError("invalid")
ValueError: invalid"""
        error, lesson, artifact = self.distiller.distill(
            log_text=tb,
            auto_register=True,
            scope="custom.api.scope"
        )
        self.assertEqual(lesson.scope, "custom.api.scope")
        self.assertIsNotNone(artifact)
        self.assertEqual(artifact.scope, "custom.api.scope")

    # 28. CLI missing file handling
    def test_cli_missing_file_handling(self):
        import argparse
        import io
        from unittest.mock import patch

        args_missing_file = argparse.Namespace(
            root=str(self.workspace_root),
            state=None,
            traceback=None,
            file="non_existent_log.txt",
            diff=None,
            diff_file=None,
            fix=None,
            auto_register=False,
            sync=None,
            scope=None,
            json=False
        )
        with patch('sys.stderr', new_callable=io.StringIO) as mock_err:
            code = cli_module.cmd_distill(args_missing_file)
            self.assertEqual(code, 1)
            self.assertIn("error: file not found", mock_err.getvalue())

    # 29. Deduplication tag and scope merging
    def test_deduplication_tag_and_scope_merging(self):
        lesson1 = DistilledLesson(
            name="Cache Key Validation",
            content="Always validate cache key format",
            scope="core.cache",
            tags=["cache", "keys"]
        )
        art1 = self.distiller.register_lesson(lesson1)
        self.assertIn("cache", art1.tags)
        self.assertIn("keys", art1.tags)

        # Update with new tag and scope
        lesson2 = DistilledLesson(
            name="Cache Key Validation",
            content="Always validate cache key format and length",
            scope="core.cache.v2",
            tags=["validation", "keys"]
        )
        art2 = self.distiller.register_lesson(lesson2)
        self.assertEqual(art1.id, art2.id)
        self.assertEqual(art2.scope, "core.cache.v2")
        self.assertIn("cache", art2.tags)
        self.assertIn("validation", art2.tags)
        self.assertIn("keys", art2.tags)
        self.assertEqual(art2.content, "Always validate cache key format and length")


if __name__ == '__main__':
    unittest.main()
