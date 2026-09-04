"""
Autonomous Error & Traceback Distiller for CookieGli.
Zero-Friction Darwin Learning Engine: extracts root causes from test failures,
panics, and runtime exceptions across Python, TypeScript/Node, Go, and Rust.
Synthesizes actionable Darwin patterns with Bayesian ROI priors and supports
deduplication, pruned resurrection, and idempotent clean sync.
"""

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from .darwin_memory import DarwinMemory, LearnedArtifact
from .adapters import TargetManager


@dataclass
class StackFrame:
    """Represents a single frame in an execution stack trace."""
    file: str
    line: int
    function: str
    code: str = ""
    is_project: bool = True


@dataclass
class DistilledError:
    """Structured distillation of a runtime error or test failure."""
    error_type: str
    error_message: str
    runner: str  # 'pytest', 'unittest', 'jest', 'go_test', 'python', 'node', 'go', 'rust', 'generic'
    root_cause_frame: Optional[StackFrame] = None
    frames: List[StackFrame] = field(default_factory=list)
    chained_errors: List['DistilledError'] = field(default_factory=list)
    raw_context: str = ""


@dataclass
class DistilledLesson:
    """Actionable evolutionary learning synthesized from error analysis and diff/fix."""
    name: str
    artifact_type: str = "lesson"
    content: str = ""
    scope: str = "global"
    tags: List[str] = field(default_factory=list)
    roi: float = 0.53
    success_rate: float = 0.67
    error_summary: str = ""
    source_file: str = ""
    source_line: int = 0


def clean_darwin_summary(raw_text: str) -> str:
    """
    Strips outer tags (<!-- darwin:... -->) and duplicate h3/h2 headers (### 🧬 ...)
    before syncing to agent configuration files to prevent duplicate headings and nested comments.
    """
    if not raw_text:
        return "- *No verified patterns evolved yet. Run tasks to build evolutionary memory.*"

    # Strip bounding comments
    cleaned = re.sub(r'<!--\s*(?:cookie|darwin)[\w:\-]*\s*-->', '', raw_text, flags=re.IGNORECASE)

    # Strip any lines that are headers matching ### 🧬 or ## System Priors / Learned Best Practices
    lines = []
    for line in cleaned.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Skip headers
        if re.match(r'^#{1,4}\s*(?:🧬|Darwin|System|Operational|Learned|Verified)', stripped, flags=re.IGNORECASE):
            continue
        lines.append(stripped)

    if not lines:
        return "- *No verified patterns evolved yet. Run tasks to build evolutionary memory.*"

    return "\n".join(lines)


def resolve_darwin_state_path(workspace_root: Union[str, Path], state_file: Optional[Union[str, Path]] = None) -> Path:
    """
    Unified state file resolution:
    - If explicit state_file provided, use it.
    - Priority 1: workspace_root / .cookiegli / darwin_state.json (if exists)
    - Priority 2: workspace_root / .agents / .darwin_state.json (if exists)
    - Fallback: workspace_root / .cookiegli / darwin_state.json (target for new creations)
    """
    if state_file:
        return Path(state_file).resolve()
    ws = Path(workspace_root).resolve()
    p1 = ws / ".cookiegli" / "darwin_state.json"
    p2 = ws / ".agents" / ".darwin_state.json"
    if p1.exists():
        return p1
    if p2.exists():
        return p2
    return p1


class ErrorDistiller:
    """Autonomous error, traceback, and panic distiller with zero-friction Darwin learning."""

    def __init__(
        self,
        workspace_root: Optional[Union[str, Path]] = None,
        state_file: Optional[Union[str, Path]] = None,
        memory: Optional[DarwinMemory] = None
    ):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.state_file = resolve_darwin_state_path(self.workspace_root, state_file)
        if memory is not None:
            self.memory = memory
        else:
            self.memory = DarwinMemory(state_file=str(self.state_file))

    def clean_log(self, text: str) -> str:
        """Strip ANSI escape codes, normalize CRLF line endings, and window to 3000 lines."""
        if not text:
            return ""
        # Strip ANSI escape sequences
        ansi_regex = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\].*?\x07|\x1b[()][AB012]')
        cleaned = ansi_regex.sub('', text)
        # Normalize CRLF and CR
        cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
        # Limit window to tail ~3000 lines
        lines = cleaned.split('\n')
        if len(lines) > 3000:
            lines = lines[-3000:]
        return '\n'.join(lines)

    def normalize_path(self, path_str: str) -> str:
        """Normalize Windows backslashes, strip surrounding quotes, and convert to relative POSIX path."""
        if not path_str:
            return ""
        p = path_str.strip().strip('\'"`')
        p = p.replace('\\', '/')

        # Try resolving relative to workspace_root
        try:
            abs_p = Path(p).resolve()
            try:
                rel = abs_p.relative_to(self.workspace_root)
                return str(rel).replace('\\', '/')
            except ValueError:
                pass
        except Exception:
            pass

        # Strip leading ./
        if p.startswith('./'):
            p = p[2:]
        return p

    def classify_frame(self, file_path: str) -> bool:
        """
        Filters out runtime, stdlib, and test runner internal frames.
        Returns True for genuine project source code, False for external/stdlib/runner frames.
        """
        if not file_path:
            return False
        norm = file_path.replace('\\', '/').lower()

        # Python stdlib & runner exclusions
        if 'site-packages/' in norm or 'dist-packages/' in norm:
            return False
        if re.search(r'/(?:python\d*|pypy\d*|anaconda\d*|miniconda\d*)/lib/', norm):
            return False
        if '/lib/python' in norm or 'lib/python' in norm:
            return False
        if norm.startswith('<frozen ') or norm.startswith('<string>'):
            return False
        if 'unittest/case.py' in norm or '/unittest/' in norm or norm.startswith('unittest/'):
            return False
        if '_pytest/' in norm or '/pytest/' in norm or norm.startswith('pytest/') or 'pluggy/' in norm:
            return False
        if 'importlib/' in norm:
            return False

        # Node / JS exclusions
        if 'node_modules/' in norm:
            return False
        if norm.startswith('node:') or 'internal/process' in norm or 'internal/modules' in norm:
            return False
        if 'jest-runner' in norm or 'jest-circus' in norm or '@jest/' in norm or 'mocha/' in norm:
            return False

        # Go runtime exclusions
        if 'src/runtime/' in norm or norm.startswith('runtime/') or norm.endswith('testing/testing.go'):
            return False

        # Rust runtime exclusions
        if 'library/std/src/' in norm or 'library/core/src/' in norm or '/rustc/' in norm:
            return False

        return True

    def parse_error(self, text: str) -> DistilledError:
        """
        3-Tier Parser Dispatch:
        Tier 1: Structured test runners (pytest, unittest, jest, go_test)
        Tier 2: Runtime panics & tracebacks (go_panic, rust_panic, python_traceback, node_stack)
        Tier 3: Generic fallback
        """
        cleaned = self.clean_log(text)

        # Tier 1 Dispatch
        res = self._parse_pytest(cleaned)
        if res:
            return res
        res = self._parse_unittest(cleaned)
        if res:
            return res
        res = self._parse_jest(cleaned)
        if res:
            return res
        res = self._parse_go_test(cleaned)
        if res:
            return res

        # Tier 2 Dispatch
        res = self._parse_go_panic(cleaned)
        if res:
            return res
        res = self._parse_rust_panic(cleaned)
        if res:
            return res
        res = self._parse_python_traceback(cleaned)
        if res:
            return res
        res = self._parse_node_stack(cleaned)
        if res:
            return res

        # Tier 3 Dispatch
        return self._parse_generic(cleaned)

    def _is_test_frame(self, file_path: str) -> bool:
        """Determines if a frame belongs to test suite rather than source under test."""
        norm = file_path.replace('\\', '/').lower()
        parts = norm.split('/')
        filename = parts[-1]
        if 'tests/' in norm or 'test/' in norm or norm.startswith('tests/') or norm.startswith('test/'):
            return True
        if filename.startswith('test_') or filename.endswith('_test.py') or filename.endswith('.test.ts') or filename.endswith('.test.js') or filename.endswith('_test.go'):
            return True
        return False

    def _select_root_cause_frame(self, frames: List[StackFrame]) -> Optional[StackFrame]:
        """
        Selects the most accurate root cause frame.
        Prefers the deepest project source frame (non-test),
        falling back to the deepest project frame, then deepest frame overall.
        """
        project_frames = [f for f in frames if f.is_project]
        if not project_frames:
            return frames[-1] if frames else None

        # Prefer non-test project frames if any exist
        non_test_frames = [
            f for f in project_frames
            if not self._is_test_frame(f.file)
        ]
        if non_test_frames:
            return non_test_frames[-1]

        return project_frames[-1]

    def _parse_pytest(self, text: str) -> Optional[DistilledError]:
        """Parses pytest execution failure logs."""
        is_pytest = (
            "pytest" in text.lower()
            or "= short test summary info =" in text
            or re.search(r'FAILED\s+[\w/\.\-]+::\w+', text)
            or re.search(r'E\s+(?:[A-Za-z_][A-Za-z0-9_]*)?(?:Error|Exception|assert):', text)
            or re.search(r'_{5,}\s*test_\w+\s*_{5,}', text)
        )
        if not is_pytest:
            return None

        # Look for summary line: FAILED tests/test_foo.py::test_bar - ErrorType: message
        summary_m = re.search(
            r'FAILED\s+([^\s:]+)(?:::([^\s\-]+))?\s+-\s+(?:((?:[A-Za-z_][A-Za-z0-9_]*)?(?:Error|Exception)):\s*(.*)|assert\s+(.*)|(.*))',
            text
        )

        error_type = "AssertionError"
        error_message = ""
        summary_file = ""
        summary_func = ""

        if summary_m:
            summary_file = summary_m.group(1) or ""
            summary_func = summary_m.group(2) or ""
            if summary_m.group(3):
                error_type = summary_m.group(3)
                error_message = (summary_m.group(4) or "").strip()
            elif summary_m.group(5):
                error_type = "AssertionError"
                error_message = f"assert {summary_m.group(5).strip()}"
            elif summary_m.group(6):
                error_message = summary_m.group(6).strip()

        # Look for explicit E lines: E   TypeError: ... or E   assert ...
        if not error_message or error_type == "AssertionError":
            e_lines = re.findall(r'^E\s+((?:[A-Za-z_][A-Za-z0-9_]*)?(?:Error|Exception)):\s*(.*)', text, re.MULTILINE)
            if e_lines:
                error_type = e_lines[-1][0]
                error_message = e_lines[-1][1].strip()
            else:
                e_assert = re.findall(r'^E\s+(?:assert\s+.*)', text, re.MULTILINE)
                if e_assert:
                    error_type = "AssertionError"
                    error_message = e_assert[0][2:].strip()

        # Parse stack frames in pytest output:
        # e.g.: path/to/file.py:123: in func
        frames: List[StackFrame] = []
        pytest_frame_re = re.compile(r'^((?:[a-zA-Z]:)?[a-zA-Z0-9_\-/\.\\]+\.[a-zA-Z0-9_]+):(\d+):\s+(?:in\s+([^\n]+)|([A-Za-z_][A-Za-z0-9_]*Error.*))', re.MULTILINE)
        for fm in pytest_frame_re.finditer(text):
            f_path = self.normalize_path(fm.group(1))
            f_line = int(fm.group(2))
            f_func = fm.group(3) or fm.group(4) or ""
            is_proj = self.classify_frame(f_path)
            frames.append(StackFrame(file=f_path, line=f_line, function=f_func, is_project=is_proj))

        # Also check standard File "...", line frames
        py_frame_re = re.compile(r'File\s+"([^"]+)",\s*line\s*(\d+)(?:,\s*in\s+(.+))?', re.MULTILINE)
        for fm in py_frame_re.finditer(text):
            f_path = self.normalize_path(fm.group(1))
            f_line = int(fm.group(2))
            f_func = fm.group(3) or ""
            is_proj = self.classify_frame(f_path)
            frames.append(StackFrame(file=f_path, line=f_line, function=f_func, is_project=is_proj))

        if not frames and summary_file:
            norm_file = self.normalize_path(summary_file)
            frames.append(StackFrame(file=norm_file, line=1, function=summary_func, is_project=self.classify_frame(norm_file)))

        root_cause = self._select_root_cause_frame(frames)
        return DistilledError(
            error_type=error_type,
            error_message=error_message,
            runner="pytest",
            root_cause_frame=root_cause,
            frames=frames,
            raw_context=text[:1000]
        )

    def _parse_unittest(self, text: str) -> Optional[DistilledError]:
        """Parses Python unittest output (FAIL: test_x or ERROR: test_y)."""
        m = re.search(r'^(?:FAIL|ERROR):\s+([^\s\(]+)\s*(?:\(([^\)]+)\))?', text, re.MULTILINE)
        if not m and "Ran " not in text:
            return None
        if not m and not ("FAILED (failures=" in text or "FAILED (errors=" in text):
            return None

        test_func = m.group(1) if m else ""
        test_case = m.group(2) if m else ""

        # Delegate traceback parsing to python traceback parser
        py_err = self._parse_python_traceback(text)
        if py_err:
            py_err.runner = "unittest"
            return py_err

        # If no traceback found, check for assertion line
        err_m = re.search(r'((?:[A-Za-z_][A-Za-z0-9_]*)?(?:Error|Exception)):\s*(.*)', text)
        error_type = err_m.group(1) if err_m else "AssertionError"
        error_msg = err_m.group(2).strip() if err_m else f"Test {test_func} failed"

        frame = StackFrame(file=self.normalize_path(test_case.replace('.', '/') + '.py') if test_case else "", line=1, function=test_func)
        return DistilledError(
            error_type=error_type,
            error_message=error_msg,
            runner="unittest",
            root_cause_frame=frame,
            frames=[frame],
            raw_context=text[:1000]
        )

    def _parse_python_traceback(self, text: str) -> Optional[DistilledError]:
        """Parses standard Python tracebacks, chained exceptions, and SyntaxError/IndentationError."""
        has_tb = "Traceback (most recent call last):" in text
        has_syntax = bool(re.search(r'(?:SyntaxError|IndentationError):\s*.*', text))

        if not has_tb and not has_syntax:
            return None

        # Check for chained exceptions
        chain_splits = re.split(
            r'\n\s*(?:During handling of the above exception, another exception occurred:|The above exception was the direct cause of the following exception:)\s*\n',
            text
        )

        if len(chain_splits) > 1:
            parsed_chain = []
            for chunk in chain_splits:
                sub_err = self._parse_single_python_traceback(chunk)
                if sub_err:
                    parsed_chain.append(sub_err)
            if parsed_chain:
                primary_err = parsed_chain[-1]
                primary_err.chained_errors = parsed_chain[:-1]
                return primary_err

        return self._parse_single_python_traceback(text)

    def _parse_single_python_traceback(self, text: str) -> Optional[DistilledError]:
        frames: List[StackFrame] = []
        frame_pattern = re.compile(
            r'^\s*File\s+"([^"]+)",\s*line\s*(\d+)(?:,\s*in\s+([^\n]+))?(?:\n[ \t]+(?!\s*File\s+)(?![A-Za-z_][\w\.]*(?:Error|Exception|Exit|Interrupt):)(.+))?',
            re.MULTILINE
        )

        for match in frame_pattern.finditer(text):
            raw_file = match.group(1)
            line_no = int(match.group(2))
            func_name = (match.group(3) or "").strip()
            code_line = (match.group(4) or "").strip()
            norm_file = self.normalize_path(raw_file)
            is_proj = self.classify_frame(norm_file)
            frames.append(StackFrame(
                file=norm_file,
                line=line_no,
                function=func_name,
                code=code_line,
                is_project=is_proj
            ))

        # Error type and message at the end
        err_m = re.search(
            r'^((?:[A-Za-z_][A-Za-z0-9_\.]*)?(?:Error|Exception|Exit|Interrupt|Warning))(?::\s*(.*))?$',
            text,
            re.MULTILINE
        )

        if err_m:
            error_type = err_m.group(1).split('.')[-1]
            error_message = (err_m.group(2) or "").strip()
        else:
            gen_m = re.search(r'((?:[A-Za-z_][A-Za-z0-9_]*)?Error)(?::\s*(.*))?', text)
            if gen_m:
                error_type = gen_m.group(1)
                error_message = (gen_m.group(2) or "").strip()
            else:
                error_type = "RuntimeError"
                error_message = "Unknown python error"

        root_cause = self._select_root_cause_frame(frames)
        return DistilledError(
            error_type=error_type,
            error_message=error_message,
            runner="python",
            root_cause_frame=root_cause,
            frames=frames,
            raw_context=text[:1000]
        )

    def _parse_jest(self, text: str) -> Optional[DistilledError]:
        """Parses Jest test runner failure outputs."""
        is_jest = (
            "FAIL " in text
            or "expect(received)." in text
            or re.search(r'●\s+.*\s*›\s*', text)
        )
        if not is_jest:
            return None

        error_type = "AssertionError"
        error_message = ""

        if "expect(received)." in text:
            rec_m = re.search(r'Expected:\s*([^\n]+)\s*\n\s*Received:\s*([^\n]+)', text)
            if rec_m:
                error_message = f"Expected: {rec_m.group(1).strip()}, Received: {rec_m.group(2).strip()}"
            else:
                error_message = "Jest assertion expectation mismatch"
        else:
            err_m = re.search(r'((?:[A-Za-z_][A-Za-z0-9_]*)?(?:Error|Exception)):\s*([^\n]+)', text)
            if err_m:
                error_type = err_m.group(1)
                error_message = err_m.group(2).strip()

        frames: List[StackFrame] = []
        stack_re = re.compile(
            r'^\s*at\s+(?:(?P<func>[^\(\s]+)\s+\()?(?P<file>(?:[a-zA-Z]:)?[^:\(\)\n]+):(?P<line>\d+):(?P<col>\d+)\)?',
            re.MULTILINE
        )
        for sm in stack_re.finditer(text):
            norm_file = self.normalize_path(sm.group('file'))
            line_no = int(sm.group('line'))
            func = sm.group('func') or ""
            is_proj = self.classify_frame(norm_file)
            frames.append(StackFrame(file=norm_file, line=line_no, function=func, is_project=is_proj))

        fail_m = re.search(r'FAIL\s+([^\s\n]+\.[jt]sx?)', text)
        if not frames and fail_m:
            norm_file = self.normalize_path(fail_m.group(1))
            frames.append(StackFrame(file=norm_file, line=1, function="test", is_project=self.classify_frame(norm_file)))

        root_cause = self._select_root_cause_frame(frames)
        return DistilledError(
            error_type=error_type,
            error_message=error_message or "Jest test failure",
            runner="jest",
            root_cause_frame=root_cause,
            frames=frames,
            raw_context=text[:1000]
        )

    def _parse_node_stack(self, text: str) -> Optional[DistilledError]:
        """Parses Node.js / JavaScript runtime error stack traces."""
        m = re.search(r'^((?:[A-Za-z_][A-Za-z0-9_]*)?(?:Error|Exception)):\s*(.*)', text, re.MULTILINE)
        if not m:
            return None

        error_type = m.group(1)
        error_message = m.group(2).strip()

        frames: List[StackFrame] = []
        stack_re = re.compile(
            r'^\s*at\s+(?:(?P<func>[^\(\s]+)\s+\()?(?P<file>(?:[a-zA-Z]:)?[^:\(\)\n]+):(?P<line>\d+):(?P<col>\d+)\)?',
            re.MULTILINE
        )
        for sm in stack_re.finditer(text):
            norm_file = self.normalize_path(sm.group('file'))
            line_no = int(sm.group('line'))
            func = sm.group('func') or ""
            is_proj = self.classify_frame(norm_file)
            frames.append(StackFrame(file=norm_file, line=line_no, function=func, is_project=is_proj))

        if not frames:
            return None

        root_cause = self._select_root_cause_frame(frames)
        return DistilledError(
            error_type=error_type,
            error_message=error_message,
            runner="node",
            root_cause_frame=root_cause,
            frames=frames,
            raw_context=text[:1000]
        )

    def _parse_go_test(self, text: str) -> Optional[DistilledError]:
        """Parses Go test runner failure logs."""
        m = re.search(r'---\s+FAIL:\s+([^\s]+)\s+\([^\)]+\)', text)
        if not m:
            return None

        test_func = m.group(1)
        frames: List[StackFrame] = []

        det_m = re.search(r'^\s*((?:[a-zA-Z]:)?[a-zA-Z0-9_\-/\.\\]+\.go):(\d+):\s+(.*)', text, re.MULTILINE)
        if det_m:
            norm_file = self.normalize_path(det_m.group(1))
            line_no = int(det_m.group(2))
            err_msg = det_m.group(3).strip()
            is_proj = self.classify_frame(norm_file)
            frames.append(StackFrame(file=norm_file, line=line_no, function=test_func, is_project=is_proj))
        else:
            err_msg = f"Go test {test_func} failed"

        root_cause = self._select_root_cause_frame(frames)
        return DistilledError(
            error_type="TestFailure",
            error_message=err_msg,
            runner="go_test",
            root_cause_frame=root_cause,
            frames=frames,
            raw_context=text[:1000]
        )

    def _parse_go_panic(self, text: str) -> Optional[DistilledError]:
        """Parses Go runtime panics."""
        m = re.search(r'^panic:\s*(?:runtime error:\s*)?(.*)', text, re.MULTILINE)
        if not m:
            return None

        error_message = m.group(1).strip()
        error_type = "panic"
        if "index out of range" in error_message:
            error_type = "IndexOutOfRange"
        elif "nil pointer" in error_message:
            error_type = "NilPointerDereference"

        frames: List[StackFrame] = []
        go_re = re.compile(r'^\s*([a-zA-Z0-9_\-\.\/]+\.[a-zA-Z0-9_]+)\(.*\)\n\s+((?:[a-zA-Z]:)?[^\n:]+):(\d+)(?:\s+\+0x[0-9a-f]+)?', re.MULTILINE)
        for gm in go_re.finditer(text):
            func_name = gm.group(1)
            raw_file = gm.group(2).strip()
            line_no = int(gm.group(3))
            norm_file = self.normalize_path(raw_file)
            is_proj = self.classify_frame(norm_file)
            frames.append(StackFrame(file=norm_file, line=line_no, function=func_name, is_project=is_proj))

        root_cause = self._select_root_cause_frame(frames)
        return DistilledError(
            error_type=error_type,
            error_message=error_message,
            runner="go",
            root_cause_frame=root_cause,
            frames=frames,
            raw_context=text[:1000]
        )

    def _parse_rust_panic(self, text: str) -> Optional[DistilledError]:
        """Parses Rust panics and backtraces."""
        m = re.search(r"thread\s+'[^']+'\s+panicked\s+at\s+'([^']+)',\s*((?:[a-zA-Z]:)?[^:]+):(\d+):(\d+)", text)
        if not m:
            return None

        error_message = m.group(1).strip()
        raw_file = m.group(2).strip()
        line_no = int(m.group(3))
        norm_file = self.normalize_path(raw_file)

        error_type = "Panic"
        err_lower = error_message.lower()
        if "index out of bounds" in err_lower:
            error_type = "IndexOutOfBounds"
        elif "unwrap" in err_lower and "none" in err_lower:
            error_type = "UnwrapNone"

        frames: List[StackFrame] = []
        bt_re = re.compile(r'^\s*\d+:\s+([^\n]+)\n\s+at\s+((?:[a-zA-Z]:)?[^:]+):(\d+):(\d+)', re.MULTILINE)
        for bm in bt_re.finditer(text):
            func_name = bm.group(1).strip()
            b_file = self.normalize_path(bm.group(2).strip())
            b_line = int(bm.group(3))
            is_proj = self.classify_frame(b_file)
            frames.append(StackFrame(file=b_file, line=b_line, function=func_name, is_project=is_proj))

        if not frames:
            is_proj = self.classify_frame(norm_file)
            frames.append(StackFrame(file=norm_file, line=line_no, function="panic", is_project=is_proj))

        root_cause = self._select_root_cause_frame(frames)
        return DistilledError(
            error_type=error_type,
            error_message=error_message,
            runner="rust",
            root_cause_frame=root_cause,
            frames=frames,
            raw_context=text[:1000]
        )

    def _parse_generic(self, text: str) -> DistilledError:
        """Generic fallback parser for unstructured errors."""
        err_m = re.search(r'(?:^|\n)(?:FATAL|ERROR|Exception|Error|panic|FAIL)[\s:]+([^\n]+)', text, re.IGNORECASE)
        error_msg = err_m.group(1).strip() if err_m else (text.strip().split('\n')[-1] if text.strip() else "Unknown error")

        type_m = re.search(r'((?:[A-Za-z_][A-Za-z0-9_]*)?(?:Error|Exception|Panic))', error_msg)
        error_type = type_m.group(1) if type_m else "RuntimeError"

        file_m = re.search(r'((?:[a-zA-Z]:)?[a-zA-Z0-9_\-/\.\\]+\.[a-zA-Z0-9_]+)[:\(](\d+)[\):]?', text)
        frames: List[StackFrame] = []
        if file_m:
            norm_file = self.normalize_path(file_m.group(1))
            line_no = int(file_m.group(2))
            is_proj = self.classify_frame(norm_file)
            frames.append(StackFrame(file=norm_file, line=line_no, function="unknown", is_project=is_proj))

        root_cause = self._select_root_cause_frame(frames)
        return DistilledError(
            error_type=error_type,
            error_message=error_msg,
            runner="generic",
            root_cause_frame=root_cause,
            frames=frames,
            raw_context=text[:1000]
        )

    def infer_domain_scope(
        self,
        error: DistilledError,
        file_path: Optional[str] = None,
        diff_text: Optional[str] = None
    ) -> str:
        """Heuristically infers the domain scope namespace."""
        target_file = file_path or (error.root_cause_frame.file if error.root_cause_frame else "")
        combined = f"{target_file} {error.error_type} {error.error_message} {diff_text or ''}".lower()

        # Cache heuristics (takes priority over storage.sqlite when cache is involved)
        if any(k in combined for k in ['ast_cache', 'cache_db']) or 'cache' in target_file.lower():
            return 'core.cache'
        if any(k in combined for k in ['blast', 'blast_radius', 'ingress']):
            return 'git.blast'
        if any(k in combined for k in ['sqlite', 'wal', 'b-tree', 'btree', 'database']):
            return 'storage.sqlite'
        if 'cache' in combined:
            return 'core.cache'
        if any(k in combined for k in ['ast_scanner', 'skeleton', 'skeletonizer', 'visitor', 'unparse', 'indentation']) or re.search(r'\bast\b', combined):
            return 'engine.ast'
        if any(k in combined for k in ['darwin', 'memory', 'decay', 'prun', 'half_life', 'roi']):
            return 'memory.pruning'
        if any(k in combined for k in ['mcp', 'mcp_server', 'json-rpc', 'rpc', 'stdio']):
            return 'mcp.tools'
        if any(k in combined for k in ['auth', 'jwt', 'token', 'login', 'permission', 'session']):
            return 'backend.auth'
        if any(k in combined for k in ['api', 'http', 'router', 'route', 'endpoint', 'request']):
            return 'backend.api'
        if any(k in combined for k in ['ui', 'dom', 'component', 'render', 'css', 'view', 'react']):
            return 'frontend.ui'

        if target_file.startswith('src/cookiegli_core/cache_db') or 'cache' in target_file:
            return 'core.cache'
        if target_file.startswith('src/cookiegli_core/skeletonizer') or 'ast' in target_file:
            return 'engine.ast'
        if target_file.startswith('src/cookiegli_core/darwin_memory'):
            return 'memory.pruning'
        if target_file.startswith('src/cookiegli_core/blast_radius'):
            return 'git.blast'
        if target_file.startswith('src/cookiegli_core/mcp_server'):
            return 'mcp.tools'

        return 'core'

    def synthesize_lesson(
        self,
        error: DistilledError,
        diff_text: Optional[str] = None,
        fix_description: Optional[str] = None
    ) -> DistilledLesson:
        """Synthesizes an actionable evolutionary lesson with Bayesian prior."""
        target_file = error.root_cause_frame.file if error.root_cause_frame else "module"
        target_line = error.root_cause_frame.line if error.root_cause_frame else 0
        module_name = Path(target_file).stem if target_file else "Core"
        module_title = "".join(part.capitalize() for part in re.split(r'[-_]', module_name))

        added_lines = []
        if diff_text:
            for line in diff_text.splitlines():
                if line.startswith('+') and not line.startswith('+++'):
                    added_lines.append(line[1:].strip())
        diff_body = "\n".join(added_lines)

        name = ""
        content = ""
        tags = [module_name.lower(), error.error_type.lower()]

        # Pattern Recognition in Diff
        if diff_body:
            # Empty Block Guard
            if re.search(r'\bast\.Pass\(\)|\bpass\b', diff_body) and (
                'ast' in diff_body or 'class' in diff_body or 'indent' in error.error_type.lower() or 'syntax' in error.error_message.lower()
            ):
                name = f"Empty Block Invariant in {module_title}"
                content = f"Ensure placeholder or collapsed blocks contain pass or ast.Pass() to prevent {error.error_type} in {target_file}."
                tags.extend(['ast', 'syntax', 'invariant'])
            # Null Guard / Safe Navigation
            elif re.search(r'\bif\s+[\w\.]+\s+is\s+not\s+None\b|\bif\s+not\s+[\w\.]+\s*:|\bif\s+[\w\.]+\s*:\s*(?:return|continue)|\?\.', diff_body):
                name = f"Null Guard in {module_title}"
                content = f"Validate object existence with explicit null/None check before attribute access to prevent {error.error_type} in {target_file}."
                tags.extend(['guard', 'null-safety'])
            # Default Fallback / Safe Dictionary Access
            elif re.search(r'\.get\s*\(|\?\?|\|\s*\{\}|\|\s*\[\]|\bor\s+[\'\"\[\{0]', diff_body):
                name = f"Default Fallback in {module_title}"
                content = f"Provide safe default fallback values via .get() or default operators to prevent {error.error_type} in {target_file}."
                tags.extend(['fallback', 'mapping'])
            # Path Normalization
            elif re.search(r'replace\s*\(\s*[\'"]\\\\?[\'"]\s*,\s*[\'"]/[\'"]\s*\)|normpath|Path\s*\(.*\)\.resolve\(\)', diff_body):
                name = f"Cross-Platform Path Normalization in {module_title}"
                content = f"Normalize filesystem separators to forward slashes and resolve relative paths to avoid platform mismatches in {target_file}."
                tags.extend(['paths', 'windows', 'cross-platform'])
            # Bounds Guard
            elif re.search(r'\blen\s*\(|<=\s*len|< len|min\s*\(|max\s*\(', diff_body) and (
                'index' in error.error_type.lower() or 'bounds' in error.error_message.lower() or 'range' in error.error_message.lower()
            ):
                name = f"Bounds Guard in {module_title}"
                content = f"Verify index bounds against collection length before indexing to prevent {error.error_type} in {target_file}."
                tags.extend(['bounds', 'indexing'])
            # Defensive Exception Handling
            elif re.search(r'\btry\s*:|\bexcept\s+[\w\s,]+:|\bcatch\s*\(', diff_body):
                name = f"Defensive Exception Handling in {module_title}"
                content = f"Wrap fragile operations in targeted try/except blocks to gracefully handle {error.error_type} in {target_file}."
                tags.extend(['resilience', 'exceptions'])
            # Type Guard
            elif re.search(r'\bisinstance\s*\(|\btypeof\b', diff_body):
                name = f"Type Guard in {module_title}"
                content = f"Check object types with isinstance before calling specialized methods to prevent {error.error_type} in {target_file}."
                tags.extend(['types', 'guard'])

        # Explicit Fix Description synthesis
        if fix_description:
            fix_clean = fix_description.strip()
            if not name:
                name = f"{module_title} Fix: {fix_clean[:30].strip()}"
            content = f"Prevent {error.error_type} in {target_file}: {fix_clean}"
            tags.append('fix')

        # Pure Traceback Fallback
        if not name or not content:
            if error.error_type == "KeyError":
                clean_key = error.error_message.strip('\"\'')
                name = f"Safe Key Lookup in {module_title}"
                content = f"Use .get('{clean_key}', default) or verify key presence in mapping before accessing in {target_file}."
                tags.extend(['mapping', 'key-error'])
            elif error.error_type == "TypeError":
                name = f"Null Guard in {module_title}"
                content = f"Verify object is not None before attribute or method access in {target_file}:{target_line} to prevent TypeError."
                tags.extend(['null-safety', 'type-error'])
            elif "Index" in error.error_type or "bounds" in error.error_message.lower():
                name = f"Sequence Bounds Guard in {module_title}"
                content = f"Verify collection length before indexing to prevent {error.error_type} in {target_file}."
                tags.extend(['bounds', 'index-error'])
            elif error.error_type == "ZeroDivisionError":
                name = f"Non-Zero Divisor Guard in {module_title}"
                content = f"Validate divisor is non-zero before performing division in {target_file}:{target_line}."
                tags.extend(['math', 'division'])
            elif error.error_type == "FileNotFoundError":
                name = f"Path Existence Guard in {module_title}"
                content = f"Verify file existence or wrap path access in defensive check to prevent {error.error_type} in {target_file}."
                tags.extend(['io', 'filesystem'])
            elif "Syntax" in error.error_type or "Indentation" in error.error_type:
                name = f"Syntax Invariant Guard in {module_title}"
                content = f"Ensure correct indentation and syntax structure in {target_file}:{target_line} to prevent {error.error_type}."
                tags.extend(['syntax', 'indentation'])
            elif error.error_type == "AssertionError":
                name = f"Assertion Invariant in {module_title}"
                msg_hint = f" ({error.error_message})" if error.error_message else ""
                content = f"Enforce expected preconditions to prevent AssertionError{msg_hint} in {target_file}."
                tags.extend(['assertions', 'testing'])
            else:
                name = f"{error.error_type} Prevention in {module_title}"
                msg_hint = f" ({error.error_message})" if error.error_message else ""
                content = f"Address root cause in {target_file}:{target_line} to prevent {error.error_type}{msg_hint}."
                tags.append('resilience')

        scope = self.infer_domain_scope(error, file_path=target_file, diff_text=diff_text)
        return DistilledLesson(
            name=name,
            artifact_type="lesson",
            content=content,
            scope=scope,
            tags=list(dict.fromkeys(tags)),  # Deduplicate keeping order
            roi=0.53,
            success_rate=0.67,
            error_summary=f"{error.error_type}: {error.error_message}",
            source_file=target_file,
            source_line=target_line
        )

    def register_lesson(self, lesson: DistilledLesson, memory: Optional[DarwinMemory] = None) -> LearnedArtifact:
        """
        Registers a distilled lesson into Darwin Memory.
        Implements Deduplication and Pruned Resurrection with Laplace Bayesian Prior:
        - If an existing artifact matches name or (scope + content), updates content and records success.
        - If the matching artifact was pruned, it is resurrected (pruned=False).
        """
        mem = memory or self.memory
        target_name_lower = lesson.name.strip().lower()

        matched_art: Optional[LearnedArtifact] = None
        for art in mem.artifacts.values():
            if art.name.strip().lower() == target_name_lower:
                matched_art = art
                break
            if art.scope == lesson.scope and art.content.strip().lower() == lesson.content.strip().lower():
                matched_art = art
                break

        if matched_art:
            # Resurrection & Update
            if matched_art.pruned:
                matched_art.pruned = False
                matched_art.prune_reason = ""
            matched_art.content = lesson.content
            if lesson.scope and lesson.scope != "global":
                matched_art.scope = lesson.scope
            for t in lesson.tags:
                if t not in matched_art.tags:
                    matched_art.tags.append(t)
            matched_art.record_use(True)
            mem.save()
            return matched_art

        # Register new artifact
        art = mem.register(
            name=lesson.name,
            artifact_type=lesson.artifact_type,
            content=lesson.content,
            scope=lesson.scope,
            tags=lesson.tags
        )
        art.record_use(True)
        mem.save()
        return art

    def sync(
        self,
        target: str = "all",
        workspace_root: Optional[Path] = None,
        memory: Optional[DarwinMemory] = None
    ) -> Dict[str, List[str]]:
        """Synchronizes clean Darwin learnings to agent configuration files."""
        ws = (workspace_root or self.workspace_root).resolve()
        mem = memory or self.memory
        raw_summary = mem.to_markdown_summary()
        cleaned_summary = clean_darwin_summary(raw_summary)
        return TargetManager.sync(target=target, workspace_root=ws, darwin_text=cleaned_summary)

    def distill(
        self,
        log_text: str,
        diff_text: Optional[str] = None,
        fix_description: Optional[str] = None,
        auto_register: bool = False,
        sync_targets: Optional[str] = None,
        scope: Optional[str] = None
    ) -> Tuple[DistilledError, DistilledLesson, Optional[LearnedArtifact]]:
        """Full end-to-end distillation pipeline."""
        cleaned_log = self.clean_log(log_text)
        error = self.parse_error(cleaned_log)
        inferred_scope = self.infer_domain_scope(error, diff_text=diff_text)
        lesson = self.synthesize_lesson(error, diff_text=diff_text, fix_description=fix_description)
        lesson.scope = scope or lesson.scope or inferred_scope

        artifact: Optional[LearnedArtifact] = None
        if auto_register:
            artifact = self.register_lesson(lesson)

        if sync_targets:
            self.sync(target=sync_targets)

        return error, lesson, artifact
