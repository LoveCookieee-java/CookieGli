"""
CookieGli Code Skeletonizer — Semantic context compressor with AST folding and focus-symbol mode.
Provides high-density token compaction for Python, TypeScript/JavaScript, Go, Rust, Java, C#, and C++.
Zero third-party dependencies. 100% cross-platform (Windows, Linux, macOS).
"""

import ast
import dataclasses
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from .genome_engine import estimate_tokens


@dataclass
class SkeletonResult:
    """Dataclass holding the skeletonized code representation and compaction metrics."""
    file_path: str
    language: str
    skeleton: str
    tokens: int
    original_lines: int
    skeleton_lines: int
    focus_symbol: Optional[str] = None
    applied_tier: int = 1
    warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize SkeletonResult to dictionary for JSON output."""
        return {
            "file_path": self.file_path,
            "language": self.language,
            "skeleton": self.skeleton,
            "tokens": self.tokens,
            "original_lines": self.original_lines,
            "skeleton_lines": self.skeleton_lines,
            "focus_symbol": self.focus_symbol,
            "applied_tier": self.applied_tier,
            "warning": self.warning,
        }


def _splice_placeholders(unparsed_code: str, placeholders: Dict[str, Dict[str, Any]]) -> str:
    """
    Splicing engine with Relative Base Indentation Normalization.
    Calculates the delta between placeholder line indent and the first non-empty line
    of original slice, preventing IndentationError when original source uses 2 spaces, tabs,
    or custom indentation.
    """
    lines = unparsed_code.splitlines()
    output_lines: List[str] = []

    for line in lines:
        matched_sentinel = None
        for s_id in placeholders:
            if s_id in line:
                matched_sentinel = s_id
                break

        if not matched_sentinel:
            output_lines.append(line)
            continue

        info = placeholders[matched_sentinel]
        indent_len = len(line) - len(line.lstrip(' \t'))
        target_indent = line[:indent_len]
        ptype = info["type"]

        if ptype == "focus":
            raw_slice = info["raw_slice"]
            first_non_empty = next((l for l in raw_slice if l.strip()), "")
            if first_non_empty:
                orig_indent_len = len(first_non_empty) - len(first_non_empty.lstrip(' \t'))
                orig_base_indent = first_non_empty[:orig_indent_len]
                delta = len(target_indent) - len(orig_base_indent)
            else:
                orig_base_indent = ""
                delta = 0

            for orig_line in raw_slice:
                if not orig_line.strip():
                    output_lines.append("")
                elif orig_line.startswith(orig_base_indent):
                    rest = orig_line[len(orig_base_indent):].expandtabs(4)
                    output_lines.append(target_indent + rest)
                else:
                    if delta >= 0:
                        output_lines.append((' ' * delta) + orig_line.expandtabs(4))
                    else:
                        strip_cnt = min(len(orig_line) - len(orig_line.lstrip(' \t')), -delta)
                        output_lines.append(orig_line[strip_cnt:].expandtabs(4))

        elif ptype == "elision":
            body_start = info["body_start"]
            body_end = info["body_end"]
            output_lines.append(f"{target_indent}... [L{body_start}-L{body_end}]")

        elif ptype == "collapsed":
            count = info["count"]
            output_lines.append(f"{target_indent}# ... [{count} private methods collapsed]")

    return "\n".join(output_lines)


class _PythonSkeletonTransformer(ast.NodeTransformer):
    """
    AST transformer implementing semantic function folding and 4-tier token degradation.
    Maintains class_stack for qualified method matching and preserves focus symbol verbatim.
    """

    def __init__(
        self,
        source_lines: List[str],
        focus_symbol: Optional[str] = None,
        tier: int = 1,
    ):
        super().__init__()
        self.source_lines = source_lines
        self.focus_symbol = focus_symbol.rstrip('()') if focus_symbol else None
        self.tier = tier
        self.class_stack: List[str] = []
        self.placeholders: Dict[str, Dict[str, Any]] = {}
        self.sentinel_counter = 0
        self.focus_found = False

    def _is_focus(self, name: str) -> bool:
        if not self.focus_symbol:
            return False
        if name == self.focus_symbol:
            return True
        if self.class_stack:
            if f"{self.class_stack[-1]}.{name}" == self.focus_symbol:
                return True
            if f"{'.'.join(self.class_stack)}.{name}" == self.focus_symbol:
                return True
        return False

    def _extract_verbatim(self, node: Union[ast.AST, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef]) -> ast.Expr:
        self.focus_found = True
        start_line = min([d.lineno for d in getattr(node, 'decorator_list', [])] + [node.lineno])
        end_line = max(start_line, node.end_lineno or start_line)

        # Extend end_line to preserve trailing comments inside the body
        def_line = self.source_lines[node.lineno - 1]
        def_indent = len(def_line) - len(def_line.lstrip(' \t'))
        curr_idx = end_line
        last_valid_end = end_line
        while curr_idx < len(self.source_lines):
            line = self.source_lines[curr_idx]
            stripped = line.strip()
            if not stripped:
                curr_idx += 1
                continue
            indent = len(line) - len(line.lstrip(' \t'))
            if indent > def_indent and stripped.startswith('#'):
                last_valid_end = curr_idx + 1
                curr_idx += 1
            else:
                break
        end_line = last_valid_end

        raw_slice = self.source_lines[start_line - 1 : end_line]
        sentinel_id = f"__COOKIEGLI_FOCUS_SENTINEL_{self.sentinel_counter}__"
        self.sentinel_counter += 1
        self.placeholders[sentinel_id] = {
            "type": "focus",
            "raw_slice": raw_slice,
            "start_line": start_line,
            "end_line": end_line,
        }
        return ast.Expr(value=ast.Name(id=sentinel_id, ctx=ast.Load()))

    def _contains_focus(self, node: ast.AST) -> bool:
        if not self.focus_symbol:
            return False
        fs_simple = self.focus_symbol.split('.')[-1]
        for child in ast.walk(node):
            if child is not node and isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if child.name == fs_simple:
                    return True
                node_name = getattr(node, 'name', '')
                if self.class_stack and f"{'.'.join(self.class_stack + [node_name])}.{child.name}".endswith(self.focus_symbol):
                    return True
        return False

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        # Check if entire class is focus symbol
        if self._is_focus(node.name):
            return self._extract_verbatim(node)

        # Push class_stack immediately so child checks and Tier 4 checks resolve qualified names
        self.class_stack.append(node.name)
        try:
            # Handle class docstring degradation
            body_stmts = list(node.body)
            if body_stmts and isinstance(body_stmts[0], ast.Expr) and isinstance(body_stmts[0].value, ast.Constant) and isinstance(body_stmts[0].value.value, str):
                doc_str = body_stmts[0].value.value
                if self.tier == 2:
                    first_line = doc_str.strip().splitlines()[0].strip() if doc_str.strip() else ""
                    body_stmts[0] = ast.Expr(value=ast.Constant(value=first_line))
                elif self.tier >= 3:
                    body_stmts.pop(0)

            # Tier 4: Prune non-focused private methods (_helper) and collapse
            if self.tier >= 4:
                private_methods = []
                for item in body_stmts:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        m_name = item.name
                        # Check private but not dunder
                        if m_name.startswith('_') and not (m_name.startswith('__') and m_name.endswith('__')):
                            # Ensure not focus symbol or container of focus symbol
                            if not self._is_focus(m_name) and not self._contains_focus(item):
                                private_methods.append(item)

                if private_methods:
                    count = len(private_methods)
                    sentinel_id = f"__COOKIEGLI_COLLAPSED_{self.sentinel_counter}__"
                    self.sentinel_counter += 1
                    self.placeholders[sentinel_id] = {
                        "type": "collapsed",
                        "count": count,
                    }
                    # Replace first private method with placeholder, remove others
                    pruned_set = set(private_methods)
                    new_stmts = []
                    collapsed_inserted = False
                    for item in body_stmts:
                        if item in pruned_set:
                            if not collapsed_inserted:
                                new_stmts.append(ast.Expr(value=ast.Name(id=sentinel_id, ctx=ast.Load())))
                                collapsed_inserted = True
                        else:
                            new_stmts.append(item)
                    if len(new_stmts) == 1 and collapsed_inserted:
                        new_stmts.append(ast.Pass())
                    body_stmts = new_stmts

            new_body = []
            for item in body_stmts:
                res = self.visit(item)
                if res is not None:
                    if isinstance(res, list):
                        new_body.extend(res)
                    else:
                        new_body.append(res)
            node.body = new_body or [ast.Pass()]
            return node
        finally:
            self.class_stack.pop()

    def _handle_function(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef]) -> Any:
        if self._is_focus(node.name):
            return self._extract_verbatim(node)

        # Non-focused function folding
        doc_node = None
        has_docstring = False
        doc_str = ""
        body_stmts = list(node.body)

        if body_stmts and isinstance(body_stmts[0], ast.Expr) and isinstance(body_stmts[0].value, ast.Constant) and isinstance(body_stmts[0].value.value, str):
            doc_node = body_stmts[0]
            doc_str = doc_node.value.value
            has_docstring = True
            remaining_stmts = body_stmts[1:]
        else:
            remaining_stmts = body_stmts

        # Docstring tier degradation
        if has_docstring:
            if self.tier == 1:
                pass  # Full docstring kept
            elif self.tier == 2:
                first_line = doc_str.strip().splitlines()[0].strip() if doc_str.strip() else ""
                doc_node = ast.Expr(value=ast.Constant(value=first_line))
            else:  # tier >= 3
                doc_node = None
                has_docstring = False

        # If this function contains the focus symbol within a nested function/class, traverse into it
        if self._contains_focus(node):
            self.class_stack.append(node.name)
            try:
                new_body = []
                if doc_node is not None:
                    new_body.append(doc_node)
                for item in remaining_stmts:
                    res = self.visit(item)
                    if res is not None:
                        if isinstance(res, list):
                            new_body.extend(res)
                        else:
                            new_body.append(res)
                node.body = new_body or [ast.Pass()]
                return node
            finally:
                self.class_stack.pop()

        # Detect stub / docstring-only functions
        is_stub = False
        if not remaining_stmts:
            is_stub = True
        elif len(remaining_stmts) == 1:
            s = remaining_stmts[0]
            if isinstance(s, ast.Pass):
                is_stub = True
            elif isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and s.value.value is Ellipsis:
                is_stub = True

        if is_stub:
            # Stub/docstring-only function: avoid redundant dummy ellipsis
            new_body = []
            if doc_node is not None:
                new_body.append(doc_node)
            if remaining_stmts:
                new_body.append(remaining_stmts[0])
            elif not new_body:
                new_body.append(ast.Pass())
            node.body = new_body
            return node

        # Fold remaining executable body
        body_start = remaining_stmts[0].lineno
        body_end = max((s.end_lineno or s.lineno) for s in remaining_stmts)
        if body_end < body_start:
            body_end = body_start

        sentinel_id = f"__COOKIEGLI_ELISION_{self.sentinel_counter}__"
        self.sentinel_counter += 1
        self.placeholders[sentinel_id] = {
            "type": "elision",
            "body_start": body_start,
            "body_end": body_end,
        }
        elision_node = ast.Expr(value=ast.Name(id=sentinel_id, ctx=ast.Load()))

        new_body = []
        if doc_node is not None:
            new_body.append(doc_node)
        new_body.append(elision_node)
        node.body = new_body
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        return self._handle_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        return self._handle_function(node)


def _skeletonize_python_fallback(code: str, focus_symbol: Optional[str] = None, max_tokens: int = 600) -> str:
    """
    Pure-Python Indentation Fallback for Syntax Errors.
    Employs an indentation-based scanner when ast.parse throws SyntaxError.
    Folds function bodies while preserving decorators and focus symbol verbatim.
    """
    lines = code.splitlines()
    output_lines: List[str] = []
    i = 0
    n = len(lines)
    fs = focus_symbol.rstrip('()') if focus_symbol else None

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Check for decorators preceding a def
        decorator_lines = []
        curr_i = i
        while curr_i < n and lines[curr_i].strip().startswith('@'):
            decorator_lines.append(lines[curr_i])
            curr_i += 1

        target_line = lines[curr_i] if curr_i < n else ""
        def_match = re.match(r'^(\s*)(?:async\s+)?def\s+([A-Za-z0-9_]+)\b', target_line)

        if def_match:
            def_indent_str = def_match.group(1)
            def_indent = len(def_indent_str)
            func_name = def_match.group(2)
            is_focus = (fs is not None) and (func_name == fs or fs.split('.')[-1] == func_name)

            # Collect entire def header (may span multiple lines up to ':')
            header_lines = list(decorator_lines)
            header_idx = curr_i
            while header_idx < n:
                line_h = lines[header_idx]
                header_lines.append(line_h)
                if line_h.rstrip().endswith(':'):
                    break
                # Guard against missing colon syntax error:
                if header_idx + 1 < n:
                    next_line = lines[header_idx + 1]
                    next_stripped = next_line.strip()
                    if next_stripped:
                        next_indent = len(next_line) - len(next_line.lstrip(' \t'))
                        combined = "".join(header_lines)
                        open_parens = combined.count('(') - combined.count(')')
                        if next_indent > def_indent and open_parens <= 0:
                            break
                        elif next_indent <= def_indent and open_parens <= 0:
                            break
                header_idx += 1

            body_start_idx = header_idx + 1
            # Find body extent based on indentation
            body_end_idx = body_start_idx
            while body_end_idx < n:
                b_line = lines[body_end_idx]
                if not b_line.strip():
                    body_end_idx += 1
                    continue
                b_indent = len(b_line) - len(b_line.lstrip(' \t'))
                if b_indent <= def_indent:
                    break
                body_end_idx += 1

            # Adjust body_end_idx to exclude trailing blank lines
            actual_end_idx = body_end_idx - 1
            while actual_end_idx >= body_start_idx and not lines[actual_end_idx].strip():
                actual_end_idx -= 1

            if is_focus:
                # Verbatim preservation of focus symbol
                output_lines.extend(header_lines)
                for b_i in range(body_start_idx, body_end_idx):
                    output_lines.append(lines[b_i])
            else:
                output_lines.extend(header_lines)
                if actual_end_idx >= body_start_idx:
                    # Check if body starts with docstring
                    first_body = lines[body_start_idx].strip()
                    doc_end_idx = body_start_idx
                    has_doc = False
                    if first_body.startswith('"""') or first_body.startswith("'''"):
                        q = first_body[:3]
                        if first_body.count(q) >= 2 and len(first_body) > 3:
                            has_doc = True
                            output_lines.append(lines[body_start_idx])
                            doc_end_idx = body_start_idx + 1
                        else:
                            has_doc = True
                            output_lines.append(lines[body_start_idx])
                            d_scan = body_start_idx + 1
                            while d_scan <= actual_end_idx:
                                output_lines.append(lines[d_scan])
                                if q in lines[d_scan]:
                                    d_scan += 1
                                    break
                                d_scan += 1
                            doc_end_idx = d_scan

                    rem_start = doc_end_idx
                    rem_end = actual_end_idx
                    if rem_start <= rem_end:
                        # Check stub
                        non_empty_rem = [lines[idx] for idx in range(rem_start, rem_end + 1) if lines[idx].strip()]
                        if len(non_empty_rem) == 1 and non_empty_rem[0].strip() in ('pass', '...'):
                            output_lines.append(f"{def_indent_str}    {non_empty_rem[0].strip()}")
                        else:
                            s = rem_start + 1
                            e = rem_end + 1
                            output_lines.append(f"{def_indent_str}    ... [L{s}-L{e}]")
                    elif not has_doc:
                        output_lines.append(f"{def_indent_str}    pass")

            i = body_end_idx
            continue

        output_lines.append(line)
        i += 1

    return "\n".join(output_lines)


class FoldResult(str):
    """String subclass that retains metadata like focus_found for scanner callers."""
    focus_found: bool = False


class _BraceFoldScanner:
    """
    Multi-language structural brace folding engine for JS/TS, Go, Rust, Java, C#, C++.
    Guards against parameter destructuring, handles semicolon-terminated interface signatures,
    preserves nested focus symbols, and applies reverse-offset splicing with indentation preservation.
    """

    CONTROL_FLOW = {
        'if', 'for', 'while', 'switch', 'catch', 'with',
        'try', 'synchronized', 'using', 'lock', 'fixed',
    }

    @staticmethod
    def find_matching_close_brace(code: str, open_brace_pos: int) -> int:
        """Finds matching closing brace '}' ignoring strings and comments."""
        pos = open_brace_pos + 1
        brace_depth = 1
        in_str: Optional[str] = None
        in_line_comment = False
        in_block_comment = False
        n = len(code)

        while pos < n:
            if in_line_comment:
                if code[pos] == '\n':
                    in_line_comment = False
                pos += 1
                continue
            if in_block_comment:
                if code[pos:pos+2] == '*/':
                    in_block_comment = False
                    pos += 2
                    continue
                pos += 1
                continue
            if in_str:
                if code[pos] == '\\':
                    pos += 2
                    continue
                if code[pos] == in_str:
                    in_str = None
                pos += 1
                continue

            if code[pos:pos+2] == '//':
                in_line_comment = True
                pos += 2
                continue
            if code[pos:pos+2] == '/*':
                in_block_comment = True
                pos += 2
                continue

            if code[pos] in ("'", '"', '`'):
                in_str = code[pos]
                pos += 1
                continue

            if code[pos] == '{':
                brace_depth += 1
            elif code[pos] == '}':
                brace_depth -= 1
                if brace_depth == 0:
                    return pos
            pos += 1

        return -1

    @classmethod
    def scan(cls, code: str, language: str = "generic", focus_symbol: Optional[str] = None) -> FoldResult:
        """
        Scans code for function/method declarations and folds bodies using reverse-offset splicing.
        """
        n = len(code)
        pos = 0
        in_str: Optional[str] = None
        in_line_comment = False
        in_block_comment = False
        paren_depth = 0

        pending_func: Optional[Dict[str, Any]] = None
        ranges_to_fold: List[Tuple[int, int, int, int, str]] = []
        fs = focus_symbol.rstrip('()') if focus_symbol else None
        focus_found = False

        # Tracks Go receiver state
        go_receiver_type: Optional[str] = None
        is_go = language.lower() == 'go'

        while pos < n:
            # Comment handling
            if in_line_comment:
                if code[pos] == '\n':
                    in_line_comment = False
                pos += 1
                continue
            if in_block_comment:
                if code[pos:pos+2] == '*/':
                    in_block_comment = False
                    pos += 2
                    continue
                pos += 1
                continue
            # String handling
            if in_str:
                if code[pos] == '\\':
                    pos += 2
                    continue
                if code[pos] == in_str:
                    in_str = None
                pos += 1
                continue

            # Start comments
            if code[pos:pos+2] == '//':
                in_line_comment = True
                pos += 2
                continue
            if code[pos:pos+2] == '/*':
                in_block_comment = True
                pos += 2
                continue

            # Start strings
            if code[pos] in ("'", '"', '`'):
                in_str = code[pos]
                pos += 1
                continue

            # Parentheses tracking (Paren-Depth Guard)
            if code[pos] == '(':
                if paren_depth == 0:
                    # Look behind to extract function/method name and base indentation
                    pre = code[:pos].rstrip()
                    line_start = code.rfind('\n', 0, pos)
                    line_start = 0 if line_start == -1 else line_start + 1
                    line_text = code[line_start:pos]
                    indent_len = len(line_text) - len(line_text.lstrip(' \t'))
                    decl_indent = line_text[:indent_len]

                    # Container declaration guard (class/interface/enum definitions are not functions)
                    is_container_decl = bool(re.search(
                        r'^\s*(?:export\s+)?(?:default\s+)?(?:public\s+|private\s+|protected\s+|abstract\s+)?\b(class|interface|enum)\b',
                        line_text
                    ))

                    if not is_container_decl:
                        # Check generic parameter list like foo<T>(
                        if pre.endswith('>'):
                            depth = 0
                            idx = len(pre) - 1
                            while idx >= 0:
                                if pre[idx] == '>':
                                    depth += 1
                                elif pre[idx] == '<':
                                    depth -= 1
                                    if depth == 0:
                                        idx -= 1
                                        break
                                idx -= 1
                            pre = pre[:idx + 1].rstrip()

                        ident_match = re.search(r'([A-Za-z0-9_]+)$', pre)
                        # Enhanced arrow match supporting async and type annotations
                        arrow_match = re.search(
                            r'(?:(?:const|let|var)\s+)?([A-Za-z0-9_]+)\s*(?::[^=]+)?\s*=\s*(?:async\s*)?$',
                            pre
                        )

                        if arrow_match:
                            func_name = arrow_match.group(1)
                            pending_func = {
                                "name": func_name,
                                "qualified_name": func_name,
                                "indent": decl_indent,
                            }
                        elif ident_match:
                            ident = ident_match.group(1)
                            if ident not in cls.CONTROL_FLOW:
                                if is_go and ident == 'func':
                                    # This '(' is a Go receiver: func (s *Server)
                                    pass
                                else:
                                    scoped_match = re.search(r'([A-Za-z0-9_]+)::([A-Za-z0-9_]+)$', pre)
                                    if scoped_match:
                                        q_name = f"{scoped_match.group(1)}.{scoped_match.group(2)}"
                                        ident = scoped_match.group(2)
                                    else:
                                        q_name = f"{go_receiver_type}.{ident}" if (is_go and go_receiver_type) else ident
                                    pending_func = {
                                        "name": ident,
                                        "qualified_name": q_name,
                                        "indent": decl_indent,
                                    }
                                    go_receiver_type = None

                paren_depth += 1
                pos += 1
                continue

            elif code[pos] == ')':
                paren_depth = max(0, paren_depth - 1)
                if paren_depth == 0 and is_go and not pending_func:
                    # Check if closing paren of Go receiver: func (s *Server)
                    rec_match = re.search(r'func\s*\(\s*(?:[A-Za-z0-9_]+\s+)?\*?([A-Za-z0-9_]+)\s*$', code[:pos])
                    if rec_match:
                        go_receiver_type = rec_match.group(1)
                pos += 1
                continue

            # Only at paren_depth == 0 can we detect body open brace or semicolon/closing guard
            if paren_depth == 0:
                # Semicolon and closing brace guard: resets pending_func on statement end or block close
                if code[pos] in (';', '}'):
                    pending_func = None
                    pos += 1
                    continue

                if code[pos] == '{':
                    # Check unparenthesized single parameter arrow function: const double = x => {
                    if not pending_func and code[:pos].rstrip().endswith('=>'):
                        pre_arrow = code[:pos].rstrip()[:-2].rstrip()
                        single_arrow_match = re.search(
                            r'(?:(?:const|let|var)\s+)?([A-Za-z0-9_]+)\s*(?::[^=]+)?\s*=\s*(?:async\s+)?(?:[A-Za-z0-9_]+)?$',
                            pre_arrow
                        )
                        if single_arrow_match:
                            func_name = single_arrow_match.group(1)
                            line_start = code.rfind('\n', 0, pos)
                            line_start = 0 if line_start == -1 else line_start + 1
                            line_text = code[line_start:pos]
                            indent_len = len(line_text) - len(line_text.lstrip(' \t'))
                            decl_indent = line_text[:indent_len]
                            pending_func = {
                                "name": func_name,
                                "qualified_name": func_name,
                                "indent": decl_indent,
                            }

                    if pending_func:
                        func_name = pending_func["name"]
                        qualified_name = pending_func.get("qualified_name", func_name)
                        func_indent = pending_func["indent"]
                        open_brace_pos = pos

                        is_focus = False
                        if fs:
                            fs_norm = fs.replace('::', '.')
                            q_norm = qualified_name.replace('::', '.')
                            if fs in (func_name, qualified_name) or fs_norm in (func_name, q_norm) or fs_norm.split('.')[-1] == func_name:
                                is_focus = True
                                focus_found = True

                        close_brace_pos = cls.find_matching_close_brace(code, open_brace_pos)
                        if close_brace_pos != -1:
                            body_content = code[open_brace_pos + 1 : close_brace_pos]
                            contains_focus = False
                            if fs and not is_focus:
                                fs_simple = fs.replace('::', '.').split('.')[-1]
                                if re.search(rf'\b{re.escape(fs_simple)}\b', body_content):
                                    contains_focus = True

                            if not is_focus and not contains_focus:
                                if body_content.strip():
                                    first_non_ws = open_brace_pos + 1 + (len(body_content) - len(body_content.lstrip()))
                                    last_non_ws = close_brace_pos - (len(body_content) - len(body_content.rstrip()))
                                    s = code[:first_non_ws].count('\n') + 1
                                    e = code[:last_non_ws].count('\n') + 1
                                    if e < s:
                                        e = s
                                    ranges_to_fold.append((open_brace_pos, close_brace_pos, s, e, func_indent))

                                pos = close_brace_pos + 1
                                pending_func = None
                                continue
                            elif is_focus:
                                pos = close_brace_pos + 1
                                pending_func = None
                                continue
                            else:
                                # Contains focus symbol: step inside outer body so nested focus symbol is preserved
                                pending_func = None
                                pos += 1
                                continue
                        else:
                            pending_func = None
                    else:
                        # Non-function opening brace (e.g. class, struct, interface container)
                        pass

            pos += 1

        # Reverse-offset splicing: restores closing brace indentation before '}'
        ranges_to_fold.sort(key=lambda r: r[0], reverse=True)
        folded_code = code
        for open_pos, close_pos, s, e, indent in ranges_to_fold:
            replacement = f"\n{indent}    ... [L{s}-L{e}]\n{indent}"
            folded_code = folded_code[:open_pos + 1] + replacement + folded_code[close_pos:]

        result = FoldResult(folded_code)
        result.focus_found = focus_found
        return result


class CodeSkeletonizer:
    """
    High-density code skeletonizer with multi-language AST / structural folding,
    focus-symbol verbatim preservation, SQLite incremental caching, and 4-tier token budget degradation.
    """

    EXT_TO_LANG = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.go': 'go',
        '.rs': 'rust',
        '.java': 'java',
        '.cs': 'csharp',
        '.c': 'c',
        '.cpp': 'cpp',
        '.h': 'c',
        '.hpp': 'cpp',
        '.cc': 'cpp',
        '.cxx': 'cpp',
    }

    def __init__(
        self,
        workspace_root: Optional[Union[str, Path]] = None,
        use_cache: bool = True,
        cache_dir: Optional[str] = None,
    ):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.use_cache = use_cache
        self.cache_dir = Path(cache_dir) if cache_dir else (self.workspace_root / '.cookiegli')
        self.conn: Optional[sqlite3.Connection] = None
        if self.use_cache:
            self._init_cache()

    def _init_cache(self) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            db_path = self.cache_dir / 'ast_cache.db'
            self.conn = sqlite3.connect(str(db_path), timeout=30.0)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS skeleton_cache (
                    cache_key TEXT PRIMARY KEY,
                    file_path TEXT,
                    language TEXT,
                    skeleton TEXT,
                    tokens INTEGER,
                    original_lines INTEGER,
                    skeleton_lines INTEGER,
                    focus_symbol TEXT,
                    applied_tier INTEGER,
                    warning TEXT,
                    mtime REAL,
                    created_at REAL
                )
            """)
            self.conn.commit()
        except Exception:
            self.conn = None

    def close(self) -> None:
        """Release underlying SQLite resources cleanly."""
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def _infer_language(self, file_path: Union[str, Path], code: Optional[str] = None) -> str:
        suffix = Path(file_path).suffix.lower()
        if suffix in self.EXT_TO_LANG:
            return self.EXT_TO_LANG[suffix]

        if code:
            if re.search(r'^\s*(?:def|class|import|from|async\s+def)\s+', code, re.MULTILINE):
                return 'python'
            if any(marker in code for marker in ('def ', 'class ', 'import ', 'elif ')):
                return 'python'
            if re.search(r'^\s*(?:package|func)\s+', code, re.MULTILINE):
                return 'go'
            if re.search(r'\b(?:fn|impl|pub\s+fn)\b', code):
                return 'rust'
            if any(marker in code for marker in ('export interface', 'export class', ': string', ': number', 'const ', 'let ')):
                return 'typescript'
            if 'public class' in code or 'System.out.' in code:
                return 'java'

        return 'python' if suffix == '.py' else 'generic'

    def skeletonize_file(
        self,
        file_path: Union[str, Path],
        focus_symbol: Optional[str] = None,
        max_tokens: int = 600,
    ) -> SkeletonResult:
        """Skeletonizes a file from disk with incremental cache lookup."""
        path_obj = Path(file_path).resolve()
        if not path_obj.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        mtime = path_obj.stat().st_mtime
        fs_str = focus_symbol or ""
        cache_key = hashlib.sha256(f"{path_obj}:{mtime}:{fs_str}:{max_tokens}".encode('utf-8')).hexdigest()

        if self.conn:
            try:
                cur = self.conn.cursor()
                cur.execute(
                    "SELECT * FROM skeleton_cache WHERE cache_key = ? AND mtime = ?",
                    (cache_key, mtime),
                )
                row = cur.fetchone()
                if row:
                    return SkeletonResult(
                        file_path=row['file_path'],
                        language=row['language'],
                        skeleton=row['skeleton'],
                        tokens=row['tokens'],
                        original_lines=row['original_lines'],
                        skeleton_lines=row['skeleton_lines'],
                        focus_symbol=row['focus_symbol'],
                        applied_tier=row['applied_tier'],
                        warning=row['warning'],
                    )
            except Exception:
                pass

        content = path_obj.read_text(encoding='utf-8', errors='replace')
        language = self._infer_language(path_obj, content)
        result = self.skeletonize_code(
            code=content,
            language=language,
            file_path=str(path_obj),
            focus_symbol=focus_symbol,
            max_tokens=max_tokens,
        )

        if self.conn:
            try:
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO skeleton_cache (
                        cache_key, file_path, language, skeleton, tokens,
                        original_lines, skeleton_lines, focus_symbol, applied_tier,
                        warning, mtime, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cache_key,
                        result.file_path,
                        result.language,
                        result.skeleton,
                        result.tokens,
                        result.original_lines,
                        result.skeleton_lines,
                        result.focus_symbol,
                        result.applied_tier,
                        result.warning,
                        mtime,
                        time.time(),
                    ),
                )
                self.conn.commit()
            except Exception:
                pass

        return result

    def skeletonize_code(
        self,
        code: str,
        language: Optional[str] = None,
        file_path: str = "<memory>",
        focus_symbol: Optional[str] = None,
        max_tokens: int = 600,
    ) -> SkeletonResult:
        """
        Skeletonizes source code in memory with 4-tier token budget degradation.
        """
        lang = (language or self._infer_language(file_path, code)).lower()
        source_lines = code.splitlines()
        original_lines = len(source_lines)

        if lang == 'python':
            try:
                # 4-Tier token compaction loop
                last_result = None
                for tier in (1, 2, 3, 4):
                    transformer = _PythonSkeletonTransformer(
                        source_lines=source_lines,
                        focus_symbol=focus_symbol,
                        tier=tier,
                    )
                    tree = ast.parse(code)
                    new_tree = transformer.visit(tree)
                    ast.fix_missing_locations(new_tree)
                    unparsed = ast.unparse(new_tree)
                    skeleton = _splice_placeholders(unparsed, transformer.placeholders)
                    tokens = estimate_tokens(skeleton)

                    warning = None
                    if focus_symbol and not transformer.focus_found:
                        warning = f"Focus symbol '{focus_symbol}' not found in source."

                    res = SkeletonResult(
                        file_path=file_path,
                        language="python",
                        skeleton=skeleton,
                        tokens=tokens,
                        original_lines=original_lines,
                        skeleton_lines=len(skeleton.splitlines()),
                        focus_symbol=focus_symbol,
                        applied_tier=tier,
                        warning=warning,
                    )
                    last_result = res
                    if tokens <= max_tokens:
                        return res

                # If still over budget after Tier 4
                if last_result:
                    tier_warn = f"Skeleton exceeds max_tokens budget ({last_result.tokens} > {max_tokens}) at Tier 4."
                    last_result.warning = f"{last_result.warning} | {tier_warn}" if last_result.warning else tier_warn
                    return last_result

            except (SyntaxError, ValueError) as err:
                # Fallback to indentation-based scanner on syntax error
                skeleton = _skeletonize_python_fallback(code, focus_symbol=focus_symbol, max_tokens=max_tokens)
                tokens = estimate_tokens(skeleton)
                warning = f"SyntaxError in Python source ({err}); used indentation fallback."
                return SkeletonResult(
                    file_path=file_path,
                    language="python",
                    skeleton=skeleton,
                    tokens=tokens,
                    original_lines=original_lines,
                    skeleton_lines=len(skeleton.splitlines()),
                    focus_symbol=focus_symbol,
                    applied_tier=1,
                    warning=warning,
                )

        # Brace languages: JS/TS, Go, Rust, Java, C#, C++
        skeleton = _BraceFoldScanner.scan(code, language=lang, focus_symbol=focus_symbol)
        tokens = estimate_tokens(skeleton)
        warning = None
        if focus_symbol and not getattr(skeleton, 'focus_found', False):
            warning = f"Focus symbol '{focus_symbol}' not found in source."
        if tokens > max_tokens:
            budget_warn = f"Skeleton exceeds max_tokens budget ({tokens} > {max_tokens})."
            warning = f"{warning} | {budget_warn}" if warning else budget_warn

        return SkeletonResult(
            file_path=file_path,
            language=lang,
            skeleton=skeleton,
            tokens=tokens,
            original_lines=original_lines,
            skeleton_lines=len(skeleton.splitlines()),
            focus_symbol=focus_symbol,
            applied_tier=1,
            warning=warning,
        )
