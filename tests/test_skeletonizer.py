"""
Unit tests for CookieGli Semantic Code Skeletonizer and Focus-Symbol Mode.
14 comprehensive tests covering Python AST folding, focus symbol verbatim preservation,
relative indentation normalization, decorators, stubs, syntax error fallback,
TypeScript destructuring, Go receivers, Rust/Java folding, 4-tier token degradation,
CLI skeleton command, and MCP tool execution.
"""

import ast
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))
sys.path.insert(0, str(REPO_ROOT / 'cli'))

from cookiegli_core.skeletonizer import (
    CodeSkeletonizer,
    SkeletonResult,
    _PythonSkeletonTransformer,
    _BraceFoldScanner,
    _skeletonize_python_fallback,
)
from cookiegli_core.mcp_server import CookieGliMcpServer
import cookiegli


class TestCodeSkeletonizer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_python_ast_folding(self):
        """1. Python AST folding: imports, docstrings, class hierarchies, dataclass fields, type annotations."""
        py_code = (
            "import os\n"
            "from dataclasses import dataclass\n"
            "from typing import List, Optional\n"
            "\n"
            "@dataclass\n"
            "class UserConfig(BaseConfig):\n"
            "    \"\"\"User configuration entity.\"\"\"\n"
            "    user_id: str\n"
            "    max_retries: int = 3\n"
            "\n"
            "    def validate(self) -> bool:\n"
            "        \"\"\"Validate configuration settings.\"\"\"\n"
            "        if self.max_retries < 0:\n"
            "            return False\n"
            "        return True\n"
            "\n"
            "def standalone_helper(x: int) -> int:\n"
            "    \"\"\"Helper calculation.\"\"\"\n"
            "    res = x * 2\n"
            "    return res\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            res = skel.skeletonize_code(py_code, language="python")

        self.assertEqual(res.language, "python")
        self.assertEqual(res.applied_tier, 1)
        self.assertIn("import os", res.skeleton)
        self.assertIn("from dataclasses import dataclass", res.skeleton)
        self.assertIn("class UserConfig(BaseConfig):", res.skeleton)
        self.assertIn("user_id: str", res.skeleton)
        self.assertIn("max_retries: int = 3", res.skeleton)
        self.assertIn("Validate configuration settings.", res.skeleton)
        self.assertIn("Helper calculation.", res.skeleton)
        self.assertIn("... [L", res.skeleton)
        # Ensure result unparses as valid Python
        ast.parse(res.skeleton)

    def test_verbatim_focus_symbol(self):
        """2. Verbatim focus symbol: comments, internal whitespace, and statements preserved 100%."""
        py_code = (
            "def func_one(a: int) -> int:\n"
            "    \"\"\"Func one doc.\"\"\"\n"
            "    step1 = a + 1\n"
            "    return step1\n"
            "\n"
            "def target_func(data: list) -> dict:\n"
            "    # Crucial step: filter nulls\n"
            "    clean = [x for x in data if x is not None]\n"
            "\n"
            "    # Calculate summary\n"
            "    summary = {\n"
            "        'count': len(clean),\n"
            "        'total': sum(clean)\n"
            "    }\n"
            "    return summary\n"
            "\n"
            "def func_three(b: str) -> str:\n"
            "    \"\"\"Func three doc.\"\"\"\n"
            "    return b.upper()\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            res = skel.skeletonize_code(py_code, focus_symbol="target_func")

        self.assertIn("# Crucial step: filter nulls", res.skeleton)
        self.assertIn("# Calculate summary", res.skeleton)
        self.assertIn("'count': len(clean)", res.skeleton)
        self.assertIn("return summary", res.skeleton)
        # func_one and func_three must be folded
        self.assertIn("... [L3-L4]", res.skeleton)
        self.assertIn("... [L19-L19]", res.skeleton)

    def test_decorators_preservation_on_focus_symbol(self):
        """3. Decorators preservation: min(d.lineno) ensures all decorators are kept on focus symbol."""
        py_code = (
            "import functools\n"
            "\n"
            "def simple_func():\n"
            "    return 1\n"
            "\n"
            "@functools.lru_cache(maxsize=128)\n"
            "@audit_decorator('admin')\n"
            "def target_action(action_name: str) -> bool:\n"
            "    # Log action execution\n"
            "    print(f'Executing: {action_name}')\n"
            "    return True\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            res = skel.skeletonize_code(py_code, focus_symbol="target_action")

        self.assertIn("@functools.lru_cache(maxsize=128)", res.skeleton)
        self.assertIn("@audit_decorator('admin')", res.skeleton)
        self.assertIn("def target_action(action_name: str) -> bool:", res.skeleton)
        self.assertIn("# Log action execution", res.skeleton)
        # simple_func is folded
        self.assertIn("simple_func():\n    ... [L4-L4]", res.skeleton)

    def test_non_standard_indentation_normalization(self):
        """4. Relative base indentation normalization: 2-space indented source spliced into AST without IndentationError."""
        py_code = (
            "class TwoSpaceService:\n"
            "  @property\n"
            "  def custom_prop(self):\n"
            "    # Custom two space comment\n"
            "    val = 10\n"
            "    return val\n"
            "\n"
            "  def another_op(self):\n"
            "    return 99\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            res = skel.skeletonize_code(py_code, focus_symbol="custom_prop")

        self.assertIn("# Custom two space comment", res.skeleton)
        self.assertIn("return val", res.skeleton)
        # Must be valid Python syntax with zero IndentationError
        parsed = ast.parse(res.skeleton)
        self.assertIsNotNone(parsed)

    def test_stub_docstring_only_functions(self):
        """5. Stub/docstring-only functions: avoid redundant dummy ellipsis on stubs and protocols."""
        py_code = (
            "class AbstractProtocol:\n"
            "    def stub_doc_only(self, a: int) -> str:\n"
            "        \"\"\"Only docstring.\"\"\"\n"
            "\n"
            "    def stub_pass(self) -> None:\n"
            "        pass\n"
            "\n"
            "    def stub_ellipsis(self) -> None:\n"
            "        ...\n"
            "\n"
            "    def real_method(self) -> int:\n"
            "        \"\"\"Real method.\"\"\"\n"
            "        x = 42\n"
            "        return x\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            res = skel.skeletonize_code(py_code)

        # Stubs should NOT have ... [L dummy ellipsis
        self.assertNotIn("stub_doc_only(self, a: int) -> str:\n        \"\"\"Only docstring.\"\"\"\n        ...", res.skeleton)
        self.assertIn("pass", res.skeleton)
        # real_method should have ... [L13-L14]
        self.assertIn("... [L13-L14]", res.skeleton)

    def test_python_syntax_error_fallback(self):
        """6. Python syntax error fallback: indentation-based structural scan on broken syntax."""
        py_code = (
            "def broken_syntax(x, y):\n"
            "    if x > 0\n"  # Missing colon
            "        return y\n"
            "    return 0\n"
            "\n"
            "def valid_function(z):\n"
            "    \"\"\"Valid function doc.\"\"\"\n"
            "    return z * 2\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            res = skel.skeletonize_code(py_code)

        self.assertIsNotNone(res.warning)
        self.assertIn("SyntaxError", res.warning)
        self.assertIn("broken_syntax(x, y):", res.skeleton)
        self.assertIn("... [L2-L4]", res.skeleton)
        self.assertIn("Valid function doc.", res.skeleton)

    def test_typescript_parameter_destructuring_and_interfaces(self):
        """7. TypeScript parameter destructuring & interface declarations."""
        ts_code = (
            "import { User, Options } from './models';\n"
            "\n"
            "export interface ApiClient {\n"
            "    fetchUser({ id, tag }: { id: string; tag?: string }): Promise<User>;\n"
            "    deleteUser(id: string): Promise<void>;\n"
            "}\n"
            "\n"
            "export class DefaultApiClient implements ApiClient {\n"
            "    private baseUrl: string;\n"
            "\n"
            "    constructor(options: Options) {\n"
            "        this.baseUrl = options.url;\n"
            "    }\n"
            "\n"
            "    async fetchUser({ id, tag }: { id: string; tag?: string }): Promise<User> {\n"
            "        const url = `${this.baseUrl}/users/${id}`;\n"
            "        return fetch(url);\n"
            "    }\n"
            "}\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            # Without focus: constructor and fetchUser folded, interface untouched
            res = skel.skeletonize_code(ts_code, language="typescript")
            self.assertIn("export interface ApiClient {", res.skeleton)
            self.assertIn("fetchUser({ id, tag }: { id: string; tag?: string }): Promise<User>;", res.skeleton)
            self.assertIn("... [L12-L12]", res.skeleton)
            self.assertIn("... [L16-L17]", res.skeleton)

            # With focus: fetchUser preserved verbatim
            res_focus = skel.skeletonize_code(ts_code, language="typescript", focus_symbol="fetchUser")
            self.assertIn("const url = `${this.baseUrl}/users/${id}`;", res_focus.skeleton)
            self.assertIn("return fetch(url);", res_focus.skeleton)
            self.assertIn("... [L12-L12]", res_focus.skeleton)

    def test_go_receiver_methods(self):
        """8. Go receiver methods: Receiver.Method qualification and folding."""
        go_code = (
            "package main\n"
            "\n"
            "type Server struct {\n"
            "    Port int\n"
            "}\n"
            "\n"
            "func NewServer(port int) *Server {\n"
            "    return &Server{Port: port}\n"
            "}\n"
            "\n"
            "func (s *Server) Start() error {\n"
            "    println(\"Running on port\", s.Port)\n"
            "    return nil\n"
            "}\n"
            "\n"
            "func (s *Server) Stop() error {\n"
            "    println(\"Server stopped\")\n"
            "    return nil\n"
            "}\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            # Focus on Go receiver method
            res = skel.skeletonize_code(go_code, language="go", focus_symbol="Server.Start")
            self.assertIn("println(\"Running on port\", s.Port)", res.skeleton)
            self.assertIn("... [L8-L8]", res.skeleton)
            self.assertIn("... [L17-L18]", res.skeleton)

    def test_rust_and_java_structural_folding(self):
        """9. Rust & Java structural folding: preserve struct/class, fold functions and constructors."""
        rust_code = (
            "struct Point {\n"
            "    x: f64,\n"
            "    y: f64,\n"
            "}\n"
            "\n"
            "impl Point {\n"
            "    pub fn new(x: f64, y: f64) -> Self {\n"
            "        Point { x, y }\n"
            "    }\n"
            "}\n"
        )
        java_code = (
            "public class Worker {\n"
            "    private String name;\n"
            "\n"
            "    public Worker(String name) {\n"
            "        this.name = name;\n"
            "    }\n"
            "\n"
            "    public void run() {\n"
            "        System.out.println(name);\n"
            "    }\n"
            "}\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            res_rust = skel.skeletonize_code(rust_code, language="rust")
            self.assertIn("struct Point {", res_rust.skeleton)
            self.assertIn("... [L8-L8]", res_rust.skeleton)

            res_java = skel.skeletonize_code(java_code, language="java")
            self.assertIn("public class Worker {", res_java.skeleton)
            self.assertIn("... [L5-L5]", res_java.skeleton)
            self.assertIn("... [L9-L9]", res_java.skeleton)

    def test_four_tier_token_budget_degradation(self):
        """10. 4-Tier token budget degradation: Tier 1 -> Tier 2 -> Tier 3 -> Tier 4 pruning."""
        py_code = (
            "class DataService:\n"
            "    \"\"\"\n"
            "    Comprehensive data service for analytics.\n"
            "    Handles complex transformations and queries.\n"
            "    \"\"\"\n"
            "    def public_action(self, val: int) -> int:\n"
            "        \"\"\"\n"
            "        Execute primary public action.\n"
            "        Validates and processes data.\n"
            "        \"\"\"\n"
            "        res = val * 10\n"
            "        return self._private_one(res)\n"
            "\n"
            "    def _private_one(self, x: int) -> int:\n"
            "        \"\"\"Private helper one.\"\"\"\n"
            "        return x + 1\n"
            "\n"
            "    def _private_two(self, y: int) -> int:\n"
            "        \"\"\"Private helper two.\"\"\"\n"
            "        return y * 2\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            # High budget: Tier 1 (full docstring, ~124 tokens)
            res1 = skel.skeletonize_code(py_code, language="python", max_tokens=2000)
            self.assertEqual(res1.applied_tier, 1)
            self.assertIn("Handles complex transformations and queries.", res1.skeleton)

            # Moderate budget: Tier 2 (1-line docstring, ~96 tokens)
            res2 = skel.skeletonize_code(py_code, language="python", max_tokens=110)
            self.assertEqual(res2.applied_tier, 2)
            self.assertIn("Execute primary public action.", res2.skeleton)
            self.assertNotIn("Validates and processes data.", res2.skeleton)

            # Low budget: Tier 3 (stripped docstrings, ~54 tokens)
            res3 = skel.skeletonize_code(py_code, language="python", max_tokens=70)
            self.assertEqual(res3.applied_tier, 3)
            self.assertNotIn("Execute primary public action.", res3.skeleton)

            # Ultra low budget: Tier 4 (prunes private methods and collapses, ~31 tokens)
            res4 = skel.skeletonize_code(py_code, language="python", max_tokens=40)
            self.assertEqual(res4.applied_tier, 4)
            self.assertIn("# ... [2 private methods collapsed]", res4.skeleton)
            self.assertNotIn("_private_one", res4.skeleton)
            self.assertNotIn("_private_two", res4.skeleton)

    def test_cli_skeleton_text(self):
        """11. CLI skeleton command (text mode)."""
        test_file = self.root / "sample.py"
        test_file.write_text(
            "def calculate(a, b):\n"
            "    '''Calculate sum.'''\n"
            "    return a + b\n",
            encoding='utf-8'
        )
        class Args:
            file_path = str(test_file)
            focus = None
            max_tokens = 600
            json = False
            no_cache = True

        out = io.StringIO()
        orig_stdout = sys.stdout
        try:
            sys.stdout = out
            ret = cookiegli.cmd_skeleton(Args())
        finally:
            sys.stdout = orig_stdout

        self.assertEqual(ret, 0)
        output_str = out.getvalue()
        self.assertIn("[SKELETON]", output_str)
        self.assertIn("sample.py", output_str)
        self.assertIn("def calculate(a, b):", output_str)

    def test_cli_skeleton_json(self):
        """12. CLI skeleton command (--json mode)."""
        test_file = self.root / "sample_json.py"
        test_file.write_text(
            "def greet(name: str) -> str:\n"
            "    return f'Hello {name}'\n",
            encoding='utf-8'
        )
        class Args:
            file_path = str(test_file)
            focus = "greet"
            max_tokens = 600
            json = True
            no_cache = True

        out = io.StringIO()
        orig_stdout = sys.stdout
        try:
            sys.stdout = out
            ret = cookiegli.cmd_skeleton(Args())
        finally:
            sys.stdout = orig_stdout

        self.assertEqual(ret, 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["language"], "python")
        self.assertEqual(data["focus_symbol"], "greet")
        self.assertIn("return f'Hello {name}'", data["skeleton"])

    def test_mcp_get_skeleton_tool(self):
        """13. MCP cookiegli_get_skeleton tool execution."""
        test_file = self.root / "mcp_sample.ts"
        test_file.write_text(
            "export function doWork(val: number): number {\n"
            "    const res = val * 3;\n"
            "    return res;\n"
            "}\n",
            encoding='utf-8'
        )
        server = CookieGliMcpServer(workspace_root=self.root)
        try:
            # Check manifest includes tool
            manifest = server.get_tools_manifest()
            tool_names = [t["name"] for t in manifest]
            self.assertIn("cookiegli_get_skeleton", tool_names)

            # Execute tool call
            result_str = server.handle_tool_call(
                "cookiegli_get_skeleton",
                {"path": str(test_file), "no_cache": True}
            )
            self.assertIn("export function doWork(val: number): number {", result_str)
            self.assertIn("... [L2-L3]", result_str)
        finally:
            server.close()

    def test_cache_hit_and_lifecycle(self):
        """14. Cache hit and clean context manager lifecycle."""
        test_file = self.root / "cache_sample.py"
        test_file.write_text(
            "def cached_func():\n"
            "    # Line 1\n"
            "    # Line 2\n"
            "    return True\n",
            encoding='utf-8'
        )
        cache_dir = self.root / ".cookiegli"
        with CodeSkeletonizer(workspace_root=self.root, use_cache=True, cache_dir=str(cache_dir)) as skel:
            # First call populates cache
            res1 = skel.skeletonize_file(test_file)
            self.assertIn("... [L", res1.skeleton)

            # Second call hits cache
            res2 = skel.skeletonize_file(test_file)
            self.assertEqual(res1.skeleton, res2.skeleton)
            self.assertEqual(res1.tokens, res2.tokens)

        # Context manager exited cleanly without leaving open file locks
        self.assertTrue(test_file.exists())

    def test_tier4_qualified_focus_preservation(self):
        """15. Tier 4 qualified focus preservation: DataService._private_one is kept verbatim while other private methods collapse."""
        code = (
            "class DataService:\n"
            "    \"\"\"Service docstring.\"\"\"\n"
            "    def _private_one(self, x: int) -> int:\n"
            "        # Vital internal computation\n"
            "        return x + 1\n"
            "\n"
            "    def _private_two(self, y: int) -> int:\n"
            "        return y * 2\n"
            "\n"
            "    def _private_three(self, z: int) -> int:\n"
            "        return z * 3\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            res = skel.skeletonize_code(code, focus_symbol="DataService._private_one", max_tokens=45)

        self.assertEqual(res.applied_tier, 4)
        self.assertIn("# Vital internal computation", res.skeleton)
        self.assertIn("return x + 1", res.skeleton)
        self.assertIn("# ... [2 private methods collapsed]", res.skeleton)
        self.assertIsNone(res.warning)
        ast.parse(res.skeleton)

    def test_tier4_all_private_methods_produces_valid_syntax(self):
        """16. Tier 4 all-private methods produces syntactically valid Python with pass."""
        code = (
            "class InternalOnly:\n"
            "    def _init_db(self):\n"
            "        return None\n"
            "\n"
            "    def _setup_cache(self):\n"
            "        return None\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            res = skel.skeletonize_code(code, max_tokens=20)

        self.assertEqual(res.applied_tier, 4)
        self.assertIn("# ... [2 private methods collapsed]", res.skeleton)
        # Must parse without IndentationError
        parsed = ast.parse(res.skeleton)
        self.assertIsNotNone(parsed)

    def test_focus_symbol_trailing_comments_preserved(self):
        """17. Trailing comments inside focus function body are preserved verbatim."""
        code = (
            "def compute_summary(data: list) -> int:\n"
            "    # Leading comment\n"
            "    total = sum(data)\n"
            "    # Critical trailing comment inside function\n"
            "\n"
            "def next_function():\n"
            "    return 10\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            res = skel.skeletonize_code(code, focus_symbol="compute_summary")

        self.assertIn("# Leading comment", res.skeleton)
        self.assertIn("total = sum(data)", res.skeleton)
        self.assertIn("# Critical trailing comment inside function", res.skeleton)
        self.assertIn("next_function():\n    ... [L7-L7]", res.skeleton)

    def test_nested_function_focus_preservation(self):
        """18. Nested function focus: inner_target is preserved verbatim inside outer_func."""
        code = (
            "def outer_func():\n"
            "    def inner_target():\n"
            "        # Inner computation\n"
            "        return 42\n"
            "    return inner_target()\n"
            "\n"
            "def other_func():\n"
            "    return 100\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            res = skel.skeletonize_code(code, focus_symbol="inner_target")

        self.assertIn("# Inner computation", res.skeleton)
        self.assertIn("return 42", res.skeleton)
        self.assertIn("other_func():\n    ... [L8-L8]", res.skeleton)
        self.assertIsNone(res.warning)

    def test_typescript_async_and_typed_arrow_functions(self):
        """19. TypeScript async & typed arrow functions are accurately identified and preserved when focused."""
        ts_code = (
            "export const add = async (a: number, b: number): Promise<number> => {\n"
            "    const sum = a + b;\n"
            "    return sum;\n"
            "};\n"
            "\n"
            "export const handleClick: React.MouseEventHandler = ({ target }) => {\n"
            "    console.log('clicked', target);\n"
            "};\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            # Focus on async arrow function
            res_add = skel.skeletonize_code(ts_code, language="typescript", focus_symbol="add")
            self.assertIn("const sum = a + b;", res_add.skeleton)
            self.assertIn("handleClick: React.MouseEventHandler = ({ target }) => {\n    ... [L7-L7]\n};", res_add.skeleton)
            self.assertIsNone(res_add.warning)

            # Focus on typed arrow function with destructuring
            res_click = skel.skeletonize_code(ts_code, language="typescript", focus_symbol="handleClick")
            self.assertIn("console.log('clicked', target);", res_click.skeleton)
            self.assertIn("... [L2-L3]", res_click.skeleton)
            self.assertIsNone(res_click.warning)

    def test_typescript_single_param_arrow_without_parens(self):
        """20. TypeScript unparenthesized single parameter arrow functions fold and focus properly."""
        ts_code = (
            "const double = x => {\n"
            "    const res = x * 2;\n"
            "    return res;\n"
            "};\n"
            "\n"
            "const triple = async val => {\n"
            "    return val * 3;\n"
            "};\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            # Non-focused: both folded
            res_all = skel.skeletonize_code(ts_code, language="typescript")
            self.assertIn("... [L2-L3]", res_all.skeleton)
            self.assertIn("... [L7-L7]", res_all.skeleton)

            # Focus on single param arrow
            res_double = skel.skeletonize_code(ts_code, language="typescript", focus_symbol="double")
            self.assertIn("const res = x * 2;", res_double.skeleton)
            self.assertIn("... [L7-L7]", res_double.skeleton)

    def test_typescript_no_semi_interface_no_leak(self):
        """21. TypeScript interface without semicolons does not leak pending_func into following class."""
        ts_code = (
            "export interface NoSemiService {\n"
            "    run(x: number): void\n"
            "    start(y: string): Promise<boolean>\n"
            "}\n"
            "\n"
            "export class RealService implements NoSemiService {\n"
            "    run(x: number): void {\n"
            "        console.log('running', x);\n"
            "    }\n"
            "\n"
            "    async start(y: string): Promise<boolean> {\n"
            "        return true;\n"
            "    }\n"
            "}\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            res = skel.skeletonize_code(ts_code, language="typescript")

        self.assertIn("export interface NoSemiService {", res.skeleton)
        self.assertIn("export class RealService implements NoSemiService {", res.skeleton)
        self.assertIn("run(x: number): void {\n        ... [L8-L8]", res.skeleton)
        self.assertIn("start(y: string): Promise<boolean> {\n        ... [L12-L12]", res.skeleton)

    def test_cpp_scoped_method_focus(self):
        """22. C++ Class::method scoping and focus symbol normalization."""
        cpp_code = (
            "#include <iostream>\n"
            "\n"
            "void MyClass::myMethod(int x) {\n"
            "    // Critical calculation\n"
            "    std::cout << x << std::endl;\n"
            "}\n"
            "\n"
            "void MyClass::otherMethod() {\n"
            "    std::cout << 'other' << std::endl;\n"
            "}\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            # Focus using Class::method
            res1 = skel.skeletonize_code(cpp_code, language="cpp", focus_symbol="MyClass::myMethod")
            self.assertIn("// Critical calculation", res1.skeleton)
            self.assertIn("... [L9-L9]", res1.skeleton)
            self.assertIsNone(res1.warning)

            # Focus using Class.method
            res2 = skel.skeletonize_code(cpp_code, language="cpp", focus_symbol="MyClass.myMethod")
            self.assertIn("// Critical calculation", res2.skeleton)
            self.assertIsNone(res2.warning)

    def test_non_python_missing_focus_symbol_warning(self):
        """23. Warning parity: non-Python languages report warning when focus_symbol is not found."""
        ts_code = "export function sample() { return 1; }"
        with CodeSkeletonizer(use_cache=False) as skel:
            res = skel.skeletonize_code(ts_code, language="typescript", focus_symbol="missingSymbol")

        self.assertIsNotNone(res.warning)
        self.assertIn("Focus symbol 'missingSymbol' not found in source.", res.warning)

    def test_python_syntax_error_fallback_missing_colon_on_def(self):
        """24. Python syntax error fallback handles missing colon on def without swallowing code."""
        py_code = (
            "def broken_def(a, b)\n"
            "    x = a + b\n"
            "    return x\n"
            "\n"
            "def normal_func(c):\n"
            "    return c * 2\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            res = skel.skeletonize_code(py_code)

        self.assertIn("broken_def(a, b)", res.skeleton)
        self.assertIn("normal_func(c):", res.skeleton)
        self.assertIn("... [L2-L3]", res.skeleton)
        self.assertIn("... [L6-L6]", res.skeleton)

    def test_control_flow_keywords_not_folded_as_functions(self):
        """25. Java try-with-resources, synchronized, and C# using/lock are not misidentified as functions."""
        java_code = (
            "public class SafeIO {\n"
            "    public void readData(String file) {\n"
            "        try (BufferedReader br = new BufferedReader(new FileReader(file))) {\n"
            "            String l = br.readLine();\n"
            "        }\n"
            "    }\n"
            "}\n"
        )
        with CodeSkeletonizer(use_cache=False) as skel:
            res = skel.skeletonize_code(java_code, language="java", focus_symbol="readData")

        self.assertIn("try (BufferedReader br = new BufferedReader(new FileReader(file))) {", res.skeleton)
        self.assertIn("String l = br.readLine();", res.skeleton)


if __name__ == '__main__':
    unittest.main()
