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
        if self.use_cache:
            try:
                from .cache_db import AstCache
                cdir = cache_dir or str(self.root_path / '.cookiegli')
                self.cache = AstCache(cdir)
            except Exception:
                self.cache = None

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
                    if (self.root_path / pkg).exists() or (self.root_path / f"{pkg}.py").exists():
                        structure.imports_internal.append(alias.name)
                    else:
                        structure.imports_external.append(pkg)

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    pkg = node.module.split('.')[0]
                    if pkg in STDLIB_PYTHON:
                        continue
                    if node.level > 0 or (self.root_path / pkg).exists() or (self.root_path / f"{pkg}.py").exists():
                        structure.imports_internal.append(node.module)
                    else:
                        structure.imports_external.append(pkg)

        structure.imports_internal = sorted(set(structure.imports_internal))
        structure.imports_external = sorted(set(structure.imports_external))

    def _parse_regex(self, content: str, structure: FileStructure, language: str):
        """Hardened multi-language parser for JS/TS, Go, Rust, Java, C#."""
        # 1. Classes, Interfaces, Traits, Structs
        class_pattern = re.compile(
            r'^\s*(?:export\s+)?(?:default\s+)?(?:public\s+|abstract\s+|final\s+|sealed\s+)*(?:class|interface|struct|trait|enum)\s+([A-Za-z0-9_]+)(?:<[^>]+>)?(?:\s+extends\s+([A-Za-z0-9_.]+))?',
            re.MULTILINE
        )
        for m in class_pattern.finditer(content):
            name = m.group(1)
            ext_str = f" extends {m.group(2)}" if m.group(2) else ""
            structure.classes.append(CodeEntity(
                name=name,
                entity_type='class',
                signature=f"{m.group(0).strip()}{ext_str}",
                line_number=content[:m.start()].count('\n') + 1,
            ))

        # 2. Standard Functions (function, def, fn, pub fn, func)
        func_pattern = re.compile(
            r'^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:public\s+|static\s+|private\s+|protected\s+)*(?:function|fn|pub\s+fn|func)\s+(?:\([A-Za-z0-9_*\s,]+\)\s+)?([A-Za-z0-9_]+)\s*\((.*?)\)(?:\s*(?:->|:)\s*([A-Za-z0-9_<>\[\]]+))?',
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

        # 3. Arrow Functions in JS/TS (const myFunc = async (args) => ...)
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

        # 4. Imports extraction
        js_imports = re.findall(r'(?:from\s+|import\s*\(?)[\'"]([^\'"]+)[\'"]', content)
        go_imports = re.findall(r'import\s+[\'"]([^\'"]+)[\'"]', content)
        java_imports = re.findall(r'import\s+(?:static\s+)?([a-zA-Z0-9_.]+);', content)
        rust_imports = re.findall(r'use\s+([a-zA-Z0-9_:]+);', content)

        all_imports = js_imports + go_imports + java_imports + rust_imports
        for imp in all_imports:
            if imp.startswith('.') or imp.startswith('/'):
                structure.imports_internal.append(imp)
            else:
                top_pkg = imp.split('/')[0] if '/' in imp else imp.split('::')[0].split('.')[0]
                structure.imports_external.append(top_pkg)

        structure.imports_internal = sorted(set(structure.imports_internal))[:15]
        structure.imports_external = sorted(set(structure.imports_external))[:15]
