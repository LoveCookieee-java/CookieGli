"""
AST and Structural Scanner for Codebases (Hardened Enterprise Grade).
Extracts classes, methods, functions, signatures, imports, and dependencies with high fidelity.
Handles Python AST, JS/TS (including arrow functions, TS interfaces, decorators), Go, Rust, Java, C/C++.
"""

import ast
import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

STDLIB_PYTHON = {
    'abc', 'argparse', 'ast', 'asyncio', 'base64', 'collections', 'concurrent',
    'contextlib', 'copy', 'csv', 'dataclasses', 'datetime', 'decimal', 'difflib',
    'enum', 'functools', 'gc', 'glob', 'hashlib', 'heapq', 'hmac', 'html', 'http',
    'importlib', 'inspect', 'io', 'itertools', 'json', 'logging', 'math', 'mimetypes',
    'multiprocessing', 'os', 'pathlib', 'pickle', 'platform', 'pprint', 'queue',
    'random', 're', 'shutil', 'signal', 'socket', 'sqlite3', 'ssl', 'stat',
    'string', 'struct', 'subprocess', 'sys', 'tempfile', 'textwrap', 'threading',
    'time', 'traceback', 'typing', 'unittest', 'urllib', 'uuid', 'warnings',
    'weakref', 'xml', 'zipfile', 'zlib'
}

IGNORED_DIRS = {
    '.git', '.svn', '.hg', 'node_modules', '__pycache__', '.venv', 'venv',
    'env', '.env', 'dist', 'build', 'target', '.idea', '.vscode', '.gemini',
    'coverage', '.next', '.nuxt', 'bin', 'obj', '.pytest_cache', 'vendor',
    'out', '.turbo'
}

MAX_FILE_SIZE_BYTES = 500 * 1024  # 500 KB limit to prevent memory spikes


@dataclass
class CodeEntity:
    name: str
    entity_type: str  # 'class', 'function', 'method', 'interface', 'struct', 'arrow_function'
    signature: str
    docstring: str = ""
    line_number: int = 0


@dataclass
class FileStructure:
    path: str
    relative_path: str
    language: str
    total_lines: int = 0
    classes: List[CodeEntity] = field(default_factory=list)
    functions: List[CodeEntity] = field(default_factory=list)
    methods: List[CodeEntity] = field(default_factory=list)
    imports_internal: List[str] = field(default_factory=list)
    imports_external: List[str] = field(default_factory=list)
    is_entry_point: bool = False
    is_minified: bool = False


class AstScanner:
    """Multi-language structural scanner with minification guards and deep syntax parsing."""

    SUPPORTED_EXTENSIONS = {
        '.py': 'Python',
        '.js': 'JavaScript',
        '.jsx': 'React JSX',
        '.ts': 'TypeScript',
        '.tsx': 'React TSX',
        '.java': 'Java',
        '.go': 'Go',
        '.rs': 'Rust',
        '.c': 'C',
        '.cpp': 'C++',
        '.h': 'C/C++ Header',
        '.hpp': 'C++ Header',
        '.cs': 'C#',
    }

    ENTRY_POINT_NAMES = {'main', 'app', 'index', 'server', 'run', 'start', '__main__', 'cli', 'wsgi', 'asgi'}

    def __init__(self, root_path: str, max_files: int = 10000, use_cache: bool = True, cache_dir: Optional[str] = None):
        self.root_path = Path(root_path).resolve()
        self.max_files = max_files
        self.use_cache = use_cache
        self.cache = None
        self.source_roots = self._discover_source_roots()
        if self.use_cache:
            try:
                from .cache_db import AstCache
                cdir = cache_dir or str(self.root_path / '.cookiegli')
                self.cache = AstCache(cdir)
            except Exception:
                self.cache = None

    def _discover_source_roots(self) -> List[Path]:
        """Discover source roots for multi-source root resolution."""
        roots = [self.root_path]
        for name in ['src', 'lib', 'app', 'packages']:
            candidate = self.root_path / name
            if candidate.is_dir():
                roots.append(candidate)
                if name == 'packages':
                    try:
                        for sub in candidate.iterdir():
                            if sub.is_dir() and not sub.name.startswith('.'):
                                roots.append(sub)
                                sub_src = sub / 'src'
                                if sub_src.is_dir():
                                    roots.append(sub_src)
                    except Exception:
                        pass
        return roots

    def _is_internal_module(self, pkg: str) -> bool:
        """Check if a module/package is internal to the project."""
        clean_pkg = pkg.replace('\\', '/').split('/')[0].split('.')[0]
        for root in self.source_roots:
            if (
                (root / clean_pkg).is_dir()
                or (root / f"{clean_pkg}.py").is_file()
                or (root / f"{clean_pkg}.ts").is_file()
                or (root / f"{clean_pkg}.tsx").is_file()
                or (root / f"{clean_pkg}.js").is_file()
                or (root / f"{clean_pkg}.jsx").is_file()
                or (root / f"{clean_pkg}.go").is_file()
                or (root / f"{clean_pkg}.rs").is_file()
                or (root / f"{clean_pkg}.java").is_file()
            ):
                return True
        return False

    def close(self) -> None:
        """Release cache resources cleanly (Windows file lock safe)."""
        if self.cache:
            try:
                self.cache.close()
            except Exception:
                pass
            self.cache = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def scan(self) -> List[FileStructure]:
        """Scan the project and return file structures with incremental caching."""
        results: List[FileStructure] = []
        active_rel_paths: List[str] = []
        scanned_count = 0

        for current_dir, dirs, files in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith('.')]

            for file_name in files:
                if scanned_count >= self.max_files:
                    break

                if file_name.endswith('.min.js') or file_name.endswith('.min.css'):
                    continue

                ext = Path(file_name).suffix.lower()
                if ext not in self.SUPPORTED_EXTENSIONS:
                    continue

                full_path = Path(current_dir) / file_name
                try:
                    rel_path = full_path.relative_to(self.root_path).as_posix()
                except ValueError:
                    rel_path = str(full_path)

                active_rel_paths.append(rel_path)

                # Incremental Cache check
                structure = None
                mtime = 0.0
                try:
                    mtime = full_path.stat().st_mtime
                except Exception:
                    pass

                if self.cache and mtime > 0:
                    cached_struct = self.cache.get(rel_path, mtime)
                    if cached_struct is not None:
                        structure = cached_struct

                if structure is None:
                    structure, sha = self._parse_file(full_path, rel_path, self.SUPPORTED_EXTENSIONS[ext])
                    if structure and self.cache and mtime > 0:
                        try:
                            self.cache.put(structure, mtime, sha)
                        except Exception:
                            pass

                if structure and not structure.is_minified:
                    results.append(structure)
                    scanned_count += 1

            if scanned_count >= self.max_files:
                break

        # Prune deleted files from cache and commit
        if self.cache:
            try:
                if active_rel_paths:
                    self.cache.prune_missing(active_rel_paths)
                self.cache.commit()
            except Exception:
                pass

        return results

    def _parse_file(self, full_path: Path, rel_path: str, language: str) -> Tuple[Optional[FileStructure], str]:
        try:
            stat = full_path.stat()
            if stat.st_size > MAX_FILE_SIZE_BYTES or stat.st_size == 0:
                return None, ""
            content = full_path.read_text(encoding='utf-8', errors='replace')
            sha = hashlib.sha256(content.encode('utf-8')).hexdigest()
        except Exception:
            return None, ""

        lines = content.splitlines()
        total_lines = len(lines)
        if total_lines == 1 and len(content) > 300:
            return FileStructure(path=str(full_path), relative_path=rel_path, language=language, is_minified=True), sha
        elif total_lines > 1 and (len(content) / total_lines) > 250:
            return FileStructure(path=str(full_path), relative_path=rel_path, language=language, is_minified=True), sha

        stem_lower = full_path.stem.lower()
        is_entry = any(entry == stem_lower or f"{entry}." in rel_path.lower() for entry in self.ENTRY_POINT_NAMES)

        structure = FileStructure(
            path=str(full_path),
            relative_path=rel_path,
            language=language,
            total_lines=total_lines,
            is_entry_point=is_entry,
        )

        if language == 'Python':
            self._parse_python(content, structure)
        else:
            self._parse_regex(content, structure, language)

        return structure, sha

    def _parse_python(self, content: str, structure: FileStructure):
        try:
            tree = ast.parse(content)
        except SyntaxError:
            self._parse_regex(content, structure, 'Python')
            return

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                bases = []
                for b in node.bases:
                    if isinstance(b, ast.Name):
                        bases.append(b.id)
                    elif isinstance(b, ast.Attribute):
                        bases.append(f"{ast.unparse(b)}")
                base_str = f"({', '.join(bases)})" if bases else ""
                doc = ast.get_docstring(node) or ""

                # Extract class methods
                methods = []
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not child.name.startswith('_') or child.name in ('__init__', '__call__'):
                            methods.append(child.name)
                            args = []
                            for a in child.args.args:
                                arg_str = a.arg
                                if a.annotation:
                                    try:
                                        arg_str += f": {ast.unparse(a.annotation)}"
                                    except Exception:
                                        pass
                                args.append(arg_str)
                            ret_str = ""
                            if child.returns:
                                try:
                                    ret_str = f" -> {ast.unparse(child.returns)}"
                                except Exception:
                                    pass

                            child_doc = ast.get_docstring(child) or ""
                            prefix = "async def" if isinstance(child, ast.AsyncFunctionDef) else "def"
                            structure.methods.append(CodeEntity(
                                name=f"{node.name}.{child.name}",
                                entity_type='method',
                                signature=f"{prefix} {child.name}({', '.join(args[:4])}){ret_str}",
                                docstring=child_doc.splitlines()[0] if child_doc else "",
                                line_number=child.lineno,
                            ))

                method_str = f" [methods: {', '.join(methods[:4])}]" if methods else ""
                entity = CodeEntity(
                    name=node.name,
                    entity_type='class',
                    signature=f"class {node.name}{base_str}{method_str}",
                    docstring=doc.splitlines()[0] if doc else "",
                    line_number=node.lineno,
                )
                structure.classes.append(entity)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith('_') or node.name in ('__init__', '__call__'):
                    args = []
                    for a in node.args.args:
                        arg_str = a.arg
                        if a.annotation:
                            try:
                                arg_str += f": {ast.unparse(a.annotation)}"
                            except Exception:
                                pass
                        args.append(arg_str)
                    ret_str = ""
                    if node.returns:
                        try:
                            ret_str = f" -> {ast.unparse(node.returns)}"
                        except Exception:
                            pass

                    doc = ast.get_docstring(node) or ""
                    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
                    entity = CodeEntity(
                        name=node.name,
                        entity_type='function',
                        signature=f"{prefix} {node.name}({', '.join(args[:4])}){ret_str}",
                        docstring=doc.splitlines()[0] if doc else "",
                        line_number=node.lineno,
                    )
                    structure.functions.append(entity)

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    pkg = alias.name.split('.')[0]
                    if pkg in STDLIB_PYTHON:
                        continue
                    if self._is_internal_module(pkg):
                        structure.imports_internal.append(alias.name)
                    else:
                        structure.imports_external.append(pkg)

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    pkg = node.module.split('.')[0]
                    if pkg in STDLIB_PYTHON:
                        continue
                    if node.level > 0 or self._is_internal_module(pkg):
                        structure.imports_internal.append(node.module)
                    else:
                        structure.imports_external.append(pkg)
                elif node.level > 0:
                    for alias in node.names:
                        structure.imports_internal.append(alias.name)

        structure.imports_internal = sorted(set(structure.imports_internal))
        structure.imports_external = sorted(set(structure.imports_external))

    def _parse_regex(self, content: str, structure: FileStructure, language: str):
        """Hardened multi-language parser for JS/TS, Go, Rust, Java, C#."""
        # 1. Classes, Interfaces, Traits, Structs
        class_pattern = re.compile(
            r'^\s*(?:export\s+)?(?:default\s+)?(?:public\s+|abstract\s+|final\s+|sealed\s+)*(?:class|interface|struct|trait|enum)\s+([A-Za-z0-9_]+)(?:<[^>]+>)?(?:\s+extends\s+([A-Za-z0-9_.]+))?',
            re.MULTILINE
        )
        class_positions = []
        for m in class_pattern.finditer(content):
            name = m.group(1)
            ext_str = f" extends {m.group(2)}" if m.group(2) else ""
            structure.classes.append(CodeEntity(
                name=name,
                entity_type='class',
                signature=f"{m.group(0).strip()}{ext_str}",
                line_number=content[:m.start()].count('\n') + 1,
            ))
            class_positions.append((m.start(), name))

        # Find class body spans for method containment
        class_spans = []  # (open_brace_idx, close_brace_idx, class_name)
        for c_start, c_name in class_positions:
            open_brace = content.find('{', c_start)
            if open_brace == -1:
                continue
            depth = 1
            pos = open_brace + 1
            n = len(content)
            while pos < n and depth > 0:
                ch = content[pos]
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                elif ch in ('"', "'", '`'):
                    quote = ch
                    pos += 1
                    while pos < n and content[pos] != quote:
                        if content[pos] == '\\':
                            pos += 1
                        pos += 1
                elif ch == '/' and pos + 1 < n and content[pos+1] == '/':
                    nl = content.find('\n', pos)
                    pos = nl if nl != -1 else n
                elif ch == '/' and pos + 1 < n and content[pos+1] == '*':
                    end_c = content.find('*/', pos + 2)
                    pos = end_c + 1 if end_c != -1 else n
                pos += 1
            class_spans.append((open_brace, pos, c_name))

        def get_container(pos: int) -> str:
            matching = [c_name for (s, e, c_name) in class_spans if s <= pos < e]
            return matching[-1] if matching else ""

        ts_java_keywords = {
            'if', 'else', 'for', 'while', 'switch', 'catch', 'finally',
            'return', 'throw', 'new', 'typeof', 'instanceof', 'function',
            'class', 'interface', 'type', 'import', 'export', 'from', 'as',
            'try', 'do', 'with', 'yield', 'await', 'case', 'default'
        }

        # 2. Go Receiver Methods: func (r *Receiver[T]) Method(...)
        go_receiver_pattern = re.compile(
            r'^\s*func\s+\(\s*(?:[A-Za-z0-9_]+\s+)?\*?([A-Za-z0-9_]+)(?:\[[^\]]+\])?\s*\)\s+([A-Za-z0-9_]+)\s*\((.*?)\)(?:\s*([^{;\n]+))?',
            re.MULTILINE
        )
        for m in go_receiver_pattern.finditer(content):
            receiver = m.group(1)
            method_name = m.group(2)
            if not method_name.startswith('_'):
                ret = f" -> {m.group(4).strip()}" if m.group(4) and m.group(4).strip() else ""
                structure.methods.append(CodeEntity(
                    name=f"{receiver}.{method_name}",
                    entity_type='method',
                    signature=f"func ({receiver}) {method_name}({m.group(3)[:30]}){ret}",
                    line_number=content[:m.start()].count('\n') + 1,
                ))

        # 3. Standard Functions (function, def, fn, pub fn, func)
        func_pattern = re.compile(
            r'^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:public\s+|static\s+|private\s+|protected\s+)*(?:function|fn|pub\s+fn|func)\s+([A-Za-z0-9_]+)(?:<[^>]+>)?\s*\((.*?)\)(?:\s*(?:->|:)\s*([A-Za-z0-9_<>\[\]]+))?',
            re.MULTILINE
        )
        for m in func_pattern.finditer(content):
            name = m.group(1)
            if not name.startswith('_'):
                ret = f" -> {m.group(3)}" if m.group(3) else ""
                structure.functions.append(CodeEntity(
                    name=name,
                    entity_type='function',
                    signature=f"{name}({m.group(2)[:30]}){ret}",
                    line_number=content[:m.start()].count('\n') + 1,
                ))

        # 4. Arrow Functions in JS/TS (const myFunc = async (args) => ...)
        arrow_pattern = re.compile(
            r'^\s*(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s+)?\((.*?)\)(?:\s*:\s*([A-Za-z0-9_<>\[\]]+))?\s*=>',
            re.MULTILINE
        )
        for m in arrow_pattern.finditer(content):
            name = m.group(1)
            if not name.startswith('_'):
                ret = f" -> {m.group(3)}" if m.group(3) else ""
                structure.functions.append(CodeEntity(
                    name=name,
                    entity_type='arrow_function',
                    signature=f"{name}({m.group(2)[:30]}){ret} =>",
                    line_number=content[:m.start()].count('\n') + 1,
                ))

        # 5. Methods for TypeScript/JavaScript inside classes
        if language in ('TypeScript', 'React TSX', 'JavaScript', 'React JSX'):
            ts_method_pattern = re.compile(
                r'^\s*(?:(?:public|private|protected|static|override|readonly|async)\s+)*(?:async\s+)?([A-Za-z0-9_]+)(?:<[^>]+>)?\s*\((.*?)\)(?:\s*:\s*([A-Za-z0-9_<>\[\]\s|&]+))?\s*\{',
                re.MULTILINE
            )
            for m in ts_method_pattern.finditer(content):
                m_name = m.group(1)
                if m_name in ts_java_keywords or m_name.startswith('_'):
                    continue
                container = get_container(m.start())
                if container:
                    full_name = f"{container}.{m_name}"
                    ret = f" -> {m.group(3).strip()}" if m.group(3) else ""
                    structure.methods.append(CodeEntity(
                        name=full_name,
                        entity_type='method',
                        signature=f"{m_name}({m.group(2)[:30]}){ret}",
                        line_number=content[:m.start()].count('\n') + 1,
                    ))

        # 6. Methods for Java/C#
        if language in ('Java', 'C#'):
            java_method_pattern = re.compile(
                r'^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:public|protected|private)\s+(?:static\s+|final\s+|synchronized\s+|abstract\s+|default\s+)*(?:<[^>]+>\s+)?(?:([A-Za-z0-9_<>\[\],\s]+?)\s+)?([A-Za-z0-9_]+)\s*\((.*?)\)\s*(?:throws\s+[A-Za-z0-9_,\s]+)?\s*[{;]',
                re.MULTILINE
            )
            for m in java_method_pattern.finditer(content):
                m_name = m.group(2)
                ret_type = m.group(1).strip() if m.group(1) else ""
                if m_name in ts_java_keywords or m_name.startswith('_'):
                    continue
                container = get_container(m.start())
                full_name = f"{container}.{m_name}" if container else m_name
                ret_str = f" -> {ret_type}" if ret_type else ""
                structure.methods.append(CodeEntity(
                    name=full_name,
                    entity_type='method',
                    signature=f"{m_name}({m.group(3)[:30]}){ret_str}",
                    line_number=content[:m.start()].count('\n') + 1,
                ))

        # 7. Imports extraction
        js_imports = re.findall(r'(?:from\s+|import\s*\(?)[\'"]([^\'"]+)[\'"]', content)
        go_imports = re.findall(r'import\s+[\'"]([^\'"]+)[\'"]', content)
        java_imports = re.findall(r'import\s+(?:static\s+)?([a-zA-Z0-9_.]+);', content)
        rust_imports = re.findall(r'use\s+([a-zA-Z0-9_:]+);', content)

        for imp in js_imports + go_imports + java_imports:
            if imp.startswith(('.', '/', '@/', '~/')):
                structure.imports_internal.append(imp)
            else:
                top_pkg = imp.split('/')[0] if '/' in imp else imp.split('.')[0]
                if self._is_internal_module(top_pkg):
                    structure.imports_internal.append(imp)
                else:
                    structure.imports_external.append(top_pkg)

        for imp in rust_imports:
            if imp.startswith(('crate::', 'super::', 'self::')) or imp in ('crate', 'super', 'self'):
                structure.imports_internal.append(imp)
            else:
                top_pkg = imp.split('::')[0]
                if top_pkg in ('crate', 'super', 'self') or self._is_internal_module(top_pkg):
                    structure.imports_internal.append(imp)
                else:
                    structure.imports_external.append(top_pkg)

        structure.imports_internal = sorted(set(structure.imports_internal))[:15]
        structure.imports_external = sorted(set(structure.imports_external))[:15]
