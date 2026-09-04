"""
CookieGli Git Blast Radius & Downstream Dependency Analyzer.
Performs forward-to-ingress dependency graph inversion, multi-stage import resolution,
cycle-safe BFS impact traversal, surgical test command synthesis, and hierarchical
inside-out token compaction (< 250 tokens).
Zero 3rd-party dependencies. 100% Cross-platform (Windows / Linux / macOS).
"""

import collections
import json
import os
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .ast_scanner import AstScanner, FileStructure, IGNORED_DIRS
from .cache_db import AstCache
from .genome_engine import estimate_tokens


def is_test_file(rel_path: str) -> bool:
    """Strictly classifies whether a file is a test file or production code."""
    norm = rel_path.replace('\\', '/').lower()
    p = Path(norm)
    name = p.name
    parts = p.parts

    # Directory checks
    if any(part in ('test', 'tests', '__tests__', 'spec', 'specs') for part in parts):
        return True

    # Filename checks
    if name.startswith('test_') or name.startswith('test-'):
        return True
    if name.endswith('_test.py') or name.endswith('-test.py'):
        return True
    if name.endswith(('.test.ts', '.test.js', '.test.tsx', '.test.jsx')):
        return True
    if name.endswith(('.spec.ts', '.spec.js', '.spec.tsx', '.spec.jsx')):
        return True
    if name.endswith('_test.go'):
        return True
    if name.endswith(('test.java', 'tests.java', 'testcase.java')):
        return True
    return False


def compute_impact_level(total_fan_out: int, fan_out_ratio: float) -> str:
    """Computes blast radius impact level (LOW, MEDIUM, HIGH, CRITICAL)."""
    if total_fan_out == 0:
        return "LOW"
    elif total_fan_out <= 2 and fan_out_ratio < 15.0:
        return "LOW"
    elif total_fan_out <= 5 and fan_out_ratio < 35.0:
        return "MEDIUM"
    elif total_fan_out <= 12 and fan_out_ratio < 60.0:
        return "HIGH"
    else:
        return "CRITICAL"


@dataclass
class BlastRadiusReport:
    """Comprehensive blast radius impact report."""
    target_files: List[str]
    impact_level: str  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    direct_consumers: List[str]  # Production code only
    transitive_consumers: List[str]  # Production code only
    targeted_tests: List[str]
    recommended_test_command: str
    affected_symbols: Dict[str, List[str]]
    total_files: int
    direct_fan_out: int
    total_fan_out: int
    fan_out_ratio: float
    detection_source: str  # 'git', 'mtime_cache', 'explicit', 'symbol'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_files": self.target_files,
            "impact_level": self.impact_level,
            "direct_consumers": self.direct_consumers,
            "transitive_consumers": self.transitive_consumers,
            "targeted_tests": self.targeted_tests,
            "recommended_test_command": self.recommended_test_command,
            "affected_symbols": self.affected_symbols,
            "total_files": self.total_files,
            "direct_fan_out": self.direct_fan_out,
            "total_fan_out": self.total_fan_out,
            "fan_out_ratio": self.fan_out_ratio,
            "detection_source": self.detection_source,
        }

    def to_compact(self, max_tokens: int = 250) -> str:
        """
        Hierarchical Inside-Out Compaction.
        Truncates transitive consumers first, direct consumers second, target files third.
        Invariant: Header, Summary, Targeted Tests, and Recommended Test Command are NEVER truncated.
        """
        header = (
            f"[BLAST_RADIUS] Impact: {self.impact_level} | "
            f"Targets: {len(self.target_files)} | "
            f"Direct: {self.direct_fan_out} | "
            f"Transitive: {len(self.transitive_consumers)} | "
            f"Source: {self.detection_source}"
        )
        summary = f"summary: Fan-out ratio: {self.fan_out_ratio:.1f}% ({self.total_fan_out}/{self.total_files} files affected)"

        test_lines = ["targeted_tests:"]
        if self.targeted_tests:
            for t in self.targeted_tests:
                test_lines.append(f"  • {t}")
        else:
            test_lines.append("  (none)")
        tests_block = "\n".join(test_lines)

        rec_cmd = f"recommended_test_command: {self.recommended_test_command}"

        def build_candidate(num_trans: int, num_direct: int, num_targets: int, include_syms: bool) -> str:
            lines = [header, summary]

            # Targets section
            if self.target_files and num_targets >= 0:
                if num_targets >= len(self.target_files):
                    lines.append(f"targets: {', '.join(self.target_files)}")
                elif num_targets > 0:
                    shown = self.target_files[:num_targets]
                    rem = len(self.target_files) - num_targets
                    lines.append(f"targets: {', '.join(shown)} (+{rem} more)")
                else:
                    lines.append(f"targets: (+{len(self.target_files)} more)")

            # Direct consumers section
            if self.direct_consumers and num_direct >= 0:
                if num_direct >= len(self.direct_consumers):
                    lines.append(f"direct_consumers: {', '.join(self.direct_consumers)}")
                elif num_direct > 0:
                    shown = self.direct_consumers[:num_direct]
                    rem = len(self.direct_consumers) - num_direct
                    lines.append(f"direct_consumers: {', '.join(shown)} (+{rem} more)")
                else:
                    lines.append(f"direct_consumers: (+{len(self.direct_consumers)} more)")

            # Transitive consumers section
            if self.transitive_consumers and num_trans >= 0:
                if num_trans >= len(self.transitive_consumers):
                    lines.append(f"transitive_consumers: {', '.join(self.transitive_consumers)}")
                elif num_trans > 0:
                    shown = self.transitive_consumers[:num_trans]
                    rem = len(self.transitive_consumers) - num_trans
                    lines.append(f"transitive_consumers: {', '.join(shown)} (+{rem} more)")
                else:
                    lines.append(f"transitive_consumers: (+{len(self.transitive_consumers)} more)")

            # Affected symbols section
            if include_syms and self.affected_symbols:
                sym_parts = []
                for f, syms in self.affected_symbols.items():
                    if syms:
                        sym_parts.append(f"{f}: {', '.join(syms)}")
                if sym_parts:
                    lines.append(f"affected_symbols: {'; '.join(sym_parts)}")

            # Invariant sections: Targeted Tests and Recommended Test Command
            lines.append(tests_block)
            lines.append(rec_cmd)
            return "\n".join(lines)

        # Full text first
        num_tr = len(self.transitive_consumers)
        num_di = len(self.direct_consumers)
        num_ta = len(self.target_files)
        inc_syms = bool(self.affected_symbols)

        text = build_candidate(num_tr, num_di, num_ta, inc_syms)
        if estimate_tokens(text) <= max_tokens:
            return text

        # Step 1: Drop affected_symbols if token limit exceeded
        if inc_syms:
            inc_syms = False
            text = build_candidate(num_tr, num_di, num_ta, inc_syms)
            if estimate_tokens(text) <= max_tokens:
                return text

        # Step 2: Truncate transitive consumers first (from num_tr down to 0)
        while num_tr > 0:
            step = max(1, num_tr // 2)
            num_tr = max(0, num_tr - step)
            text = build_candidate(num_tr, num_di, num_ta, inc_syms)
            if estimate_tokens(text) <= max_tokens:
                return text

        # Step 3: Truncate direct consumers second (from num_di down to 0)
        while num_di > 0:
            step = max(1, num_di // 2)
            num_di = max(0, num_di - step)
            text = build_candidate(num_tr, num_di, num_ta, inc_syms)
            if estimate_tokens(text) <= max_tokens:
                return text

        # Step 4: Truncate target files third (from num_ta down to 1 then 0)
        while num_ta > 1:
            step = max(1, num_ta // 2)
            num_ta = max(1, num_ta - step)
            text = build_candidate(num_tr, num_di, num_ta, inc_syms)
            if estimate_tokens(text) <= max_tokens:
                return text

        if num_ta > 0:
            num_ta = 0
            text = build_candidate(num_tr, num_di, num_ta, inc_syms)
            if estimate_tokens(text) <= max_tokens:
                return text

        # Step 5: Inside-out dropping of placeholder lines under extreme token limits
        num_tr = -1
        text = build_candidate(num_tr, num_di, num_ta, inc_syms)
        if estimate_tokens(text) <= max_tokens:
            return text

        num_di = -1
        text = build_candidate(num_tr, num_di, num_ta, inc_syms)
        if estimate_tokens(text) <= max_tokens:
            return text

        num_ta = -1
        text = build_candidate(num_tr, num_di, num_ta, inc_syms)
        if estimate_tokens(text) <= max_tokens:
            return text

        # Invariant guarantee: Header, Summary, Targeted Tests, and Recommended Test Command are NEVER truncated
        return text


class BlastRadiusEngine:
    """
    Git Blast Radius & Downstream Dependency Analyzer.
    Safe Windows WAL SQLite lifecycle management with bounded BFS traversal.
    """

    def __init__(
        self,
        root_path: str,
        use_cache: bool = True,
        cache_dir: Optional[str] = None
    ):
        self.root_path = Path(root_path).resolve()
        self.use_cache = use_cache
        self.cache_dir = Path(cache_dir).resolve() if cache_dir else (self.root_path / '.cookiegli')
        self.source_roots = self._discover_source_roots()
        self.cache: Optional[AstCache] = None
        if self.use_cache:
            try:
                self.cache = AstCache(str(self.cache_dir))
            except Exception:
                self.cache = None

    def _discover_source_roots(self) -> List[Path]:
        """Discover source roots for multi-source root resolution."""
        roots = [self.root_path]
        for name in ['src', 'lib', 'app', 'packages']:
            cand = self.root_path / name
            if cand.is_dir():
                roots.append(cand)
                if name == 'packages':
                    try:
                        for sub in cand.iterdir():
                            if sub.is_dir() and not sub.name.startswith('.'):
                                roots.append(sub)
                                sub_src = sub / 'src'
                                if sub_src.is_dir():
                                    roots.append(sub_src)
                    except Exception:
                        pass
        return roots

    def close(self) -> None:
        """Cleanly release SQLite cache connection (Windows file lock safe)."""
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

    def _parse_git_porcelain(self, stdout: str) -> List[str]:
        """Parses git status --porcelain output, capturing staged, unstaged, untracked, and deleted files."""
        changed = set()
        for line in stdout.splitlines():
            if not line or len(line) < 3 or line.startswith("!!"):
                continue
            path_part = line[3:].strip().strip('"')
            if " -> " in path_part:
                # Rename detected
                parts = [p.strip().strip('"') for p in path_part.split(" -> ")]
                for p in parts:
                    changed.add(p.replace('\\', '/'))
            else:
                p_norm = path_part.replace('\\', '/')
                target_disk = self.root_path / p_norm
                if target_disk.is_dir():
                    # Untracked directory - recursively collect supported files
                    for cur_dir, dirs, files in os.walk(target_disk):
                        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith('.')]
                        for f in files:
                            ext = Path(f).suffix.lower()
                            if ext in AstScanner.SUPPORTED_EXTENSIONS:
                                rel = (Path(cur_dir) / f).relative_to(self.root_path).as_posix()
                                changed.add(rel)
                else:
                    changed.add(p_norm)
        return sorted(list(changed))

    def _detect_changed_mtime_fallback(self) -> Tuple[List[str], str]:
        """
        Pre-scan SQLite file_cache mtime comparison against disk (os.stat().st_mtime)
        BEFORE running AstScanner.scan().
        """
        db_file = self.cache_dir / "ast_cache.db"
        changed = set()
        if db_file.exists():
            try:
                conn = sqlite3.connect(str(db_file), timeout=10.0)
                conn.row_factory = sqlite3.Row
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT path, relative_path, mtime FROM file_cache")
                    rows = cur.fetchall()
                    cached_rel_paths = set()
                    for row in rows:
                        rel = (row["relative_path"] or row["path"]).replace('\\', '/')
                        cached_rel_paths.add(rel)
                        disk_p = Path(row["path"]) if Path(row["path"]).is_absolute() else (self.root_path / rel)
                        if not disk_p.exists():
                            # Deleted file
                            changed.add(rel)
                        else:
                            try:
                                st = disk_p.stat()
                                if abs(st.st_mtime - row["mtime"]) > 1e-4:
                                    changed.add(rel)
                            except Exception:
                                pass

                    # Disk scan for untracked / newly created files not in cache
                    for cur_dir, dirs, files in os.walk(self.root_path):
                        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith('.')]
                        for f in files:
                            ext = Path(f).suffix.lower()
                            if ext in AstScanner.SUPPORTED_EXTENSIONS:
                                rel = (Path(cur_dir) / f).relative_to(self.root_path).as_posix()
                                if rel not in cached_rel_paths:
                                    changed.add(rel)
                finally:
                    conn.close()
                return sorted(list(changed)), "mtime_cache"
            except Exception:
                pass

        return [], "empty_cache"

    def detect_changed_files(self) -> Tuple[List[str], str]:
        """
        Detects modified, staged, untracked, or deleted files.
        Tries safe git status --porcelain first, falling back to pre-scan SQLite mtime comparison.
        """
        git_found = False
        cur = self.root_path
        for _ in range(3):
            if (cur / ".git").exists():
                git_found = True
                break
            if cur.parent == cur:
                break
            cur = cur.parent

        if git_found:
            try:
                env = os.environ.copy()
                env["GIT_TERMINAL_PROMPT"] = "0"
                env["GIT_PAGER"] = "cat"
                res = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=str(self.root_path),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=5.0,
                    env=env,
                    check=False
                )
                if res.returncode == 0:
                    changed = self._parse_git_porcelain(res.stdout)
                    return changed, "git"
            except Exception:
                pass

        return self._detect_changed_mtime_fallback()

    def _resolve_import(
        self,
        imp: str,
        caller_path: str,
        known_files: Set[str]
    ) -> Optional[str]:
        """
        5-stage resolution ladder with candidate extension probing.
        Probes: .py, .ts, .tsx, .js, .jsx, .go, .rs, .java, /__init__.py, /index.ts, etc.
        """
        imp = imp.strip().strip("'\"")
        if not imp:
            return None

        caller_dir = Path(caller_path).parent.as_posix()
        if caller_dir == ".":
            caller_dir = ""

        base_candidates: List[str] = []

        # Handle alias imports (@/components/Button, ~/utils)
        if imp.startswith(('@/', '~/')):
            alias_tail = imp[2:].strip('/')
            base_candidates.append(alias_tail)
            for root in self.source_roots:
                root_prefix = root.relative_to(self.root_path).as_posix() if root != self.root_path else ""
                if root_prefix:
                    base_candidates.append(f"{root_prefix}/{alias_tail}")

        # Stage 1 & 2: Relative import handling
        if imp.startswith('.'):
            if imp.startswith('./') or imp.startswith('../'):
                raw_path = f"{caller_dir}/{imp}" if caller_dir else imp
                norm_rel = os.path.normpath(raw_path).replace('\\', '/').lstrip('/')
                base_candidates.append(norm_rel)
            else:
                num_dots = len(imp) - len(imp.lstrip('.'))
                rem = imp.lstrip('.')
                rem_path = rem.replace('.', '/')
                cur = Path(caller_dir) if caller_dir else Path('.')
                for _ in range(num_dots - 1):
                    cur = cur.parent
                cur_posix = cur.as_posix()
                if cur_posix == ".":
                    cur_posix = ""
                norm_rel = f"{cur_posix}/{rem_path}".strip('/') if cur_posix else rem_path
                base_candidates.append(norm_rel)
        else:
            as_slash = imp.replace('.', '/')
            # Exact / as-is
            base_candidates.append(imp)
            base_candidates.append(as_slash)

            # Relative to caller dir
            if caller_dir:
                base_candidates.append(f"{caller_dir}/{imp}")
                base_candidates.append(f"{caller_dir}/{as_slash}")

            # Multi-source roots
            for root in self.source_roots:
                root_prefix = root.relative_to(self.root_path).as_posix() if root != self.root_path else ""
                if root_prefix:
                    base_candidates.append(f"{root_prefix}/{imp}")
                    base_candidates.append(f"{root_prefix}/{as_slash}")

        EXTS = ['.py', '.ts', '.tsx', '.js', '.jsx', '.go', '.rs', '.java']
        INDEXES = ['/__init__.py', '/index.ts', '/index.js', '/index.tsx', '/index.jsx', '/mod.rs']

        def probe(cand: str) -> Optional[str]:
            cand = cand.strip('/')
            # Direct match
            if cand in known_files:
                return cand
            # Extensions probing
            for ext in EXTS:
                with_ext = f"{cand}{ext}".lstrip('/')
                if with_ext in known_files:
                    return with_ext
            # Index / init probing
            for idx in INDEXES:
                with_idx = f"{cand}{idx}".lstrip('/')
                if with_idx in known_files:
                    return with_idx
            return None

        for base in base_candidates:
            res = probe(base)
            if res:
                return res

        # Stage 5: Symbol tail drop (e.g. module.Symbol -> module)
        for base in base_candidates:
            if '/' in base:
                parent_base, _ = base.rsplit('/', 1)
                res = probe(parent_base)
                if res:
                    return res

        return None

    def build_ingress_graph(
        self,
        files: List[FileStructure],
        extra_known_files: Optional[List[str]] = None
    ) -> Dict[str, Set[str]]:
        """
        Forward-to-ingress dependency graph inversion.
        Injects deleted target files and untracked files into the resolver lookup
        before resolving consumer imports.
        """
        known_files: Set[str] = set()
        for f in files:
            known_files.add(f.relative_path.replace('\\', '/'))
        if extra_known_files:
            for ef in extra_known_files:
                known_files.add(ef.replace('\\', '/'))

        ingress: Dict[str, Set[str]] = collections.defaultdict(set)
        for kf in known_files:
            ingress[kf] = set()

        for file_struct in files:
            caller = file_struct.relative_path.replace('\\', '/')
            all_imports = file_struct.imports_internal + file_struct.imports_external
            for imp in all_imports:
                resolved = self._resolve_import(imp, caller, known_files)
                if resolved and resolved != caller:
                    ingress[resolved].add(caller)

        return dict(ingress)

    def find_tests_for_files(
        self,
        affected_files: List[str],
        all_files: Optional[List[str]] = None
    ) -> List[str]:
        """
        Collects test files that directly match affected file stems by naming convention.
        """
        tests: List[str] = []
        if all_files is None:
            all_files = []
            for cur_dir, dirs, files in os.walk(self.root_path):
                dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith('.')]
                for f in files:
                    ext = Path(f).suffix.lower()
                    if ext in AstScanner.SUPPORTED_EXTENSIONS:
                        all_files.append((Path(cur_dir) / f).relative_to(self.root_path).as_posix())

        test_pool = [f for f in all_files if is_test_file(f)]
        for aff in affected_files:
            aff_stem = Path(aff).stem.lower()
            if aff_stem.startswith(('test_', 'test-')):
                aff_stem = aff_stem[5:]
            elif aff_stem.endswith(('_test', '-test')):
                aff_stem = aff_stem[:-5]

            for tf in test_pool:
                t_stem = Path(tf).stem.lower()
                if (
                    t_stem == f"test_{aff_stem}"
                    or t_stem == f"{aff_stem}_test"
                    or t_stem == f"test-{aff_stem}"
                    or t_stem == f"{aff_stem}-test"
                    or t_stem == aff_stem
                ):
                    if tf not in tests:
                        tests.append(tf)

        return tests

    def synthesize_test_command(self, tests: List[str], lang: Optional[str] = None) -> str:
        """
        Surgical test command synthesis.
        Probes available test runners (shutil.which('pytest'), python -m unittest).
        Defaults to python -m unittest. Fallback on empty tests: python -m unittest discover -s tests.
        """
        if not tests:
            if lang in ("typescript", "javascript"):
                return "npm test"
            elif lang == "go":
                return "go test ./..."
            elif lang == "rust":
                return "cargo test"
            elif (self.root_path / "package.json").exists() and not (self.root_path / "setup.py").exists() and not (self.root_path / "pyproject.toml").exists():
                return "npm test"
            elif (self.root_path / "go.mod").exists():
                return "go test ./..."
            elif (self.root_path / "Cargo.toml").exists():
                return "cargo test"
            return "python -m unittest discover -s tests"

        # Check explicit non-python file extensions or explicit non-python lang
        if any(t.endswith((".ts", ".js", ".tsx", ".jsx")) for t in tests) and lang != "python":
            return f"npm test -- {' '.join(tests)}"
        if any(t.endswith(".go") for t in tests) and lang != "python":
            return f"go test {' '.join(tests)}"
        if any(t.endswith(".rs") for t in tests) and lang != "python":
            return f"cargo test {' '.join(tests)}"

        is_py = lang == "python" or any(t.endswith(".py") for t in tests) or lang is None
        if is_py:
            pytest_path = shutil.which("pytest")
            if pytest_path:
                return f"pytest -v {' '.join(tests)}"
            else:
                return f"python -m unittest {' '.join(tests)}"

        return f"python -m unittest {' '.join(tests)}"

    def analyze(
        self,
        target_files: Optional[List[str]] = None,
        symbol: Optional[str] = None,
        max_depth: int = 3
    ) -> BlastRadiusReport:
        """
        Executes bounded, cycle-safe BFS impact traversal on the ingress graph.
        Partitions production consumers and targeted tests strictly.
        """
        # 1. Target files resolution
        if target_files is not None:
            norm_targets = []
            for tf in target_files:
                p = Path(tf)
                if p.is_absolute():
                    try:
                        norm_targets.append(p.resolve().relative_to(self.root_path).as_posix())
                    except ValueError:
                        norm_targets.append(p.as_posix())
                else:
                    norm_rel = os.path.normpath(tf).replace('\\', '/')
                    if norm_rel.startswith('./'):
                        norm_rel = norm_rel[2:]
                    norm_targets.append(norm_rel)
            targets = norm_targets
            detection_source = "explicit"
        elif symbol:
            targets = []
            detection_source = "symbol"
        else:
            targets, detection_source = self.detect_changed_files()

        # 2. AST scan across codebase
        with AstScanner(str(self.root_path), use_cache=self.use_cache, cache_dir=str(self.cache_dir)) as scanner:
            file_structures = scanner.scan()

        all_file_paths = [f.relative_path.replace('\\', '/') for f in file_structures]

        # 3. Symbol targeting resolution
        affected_symbols: Dict[str, List[str]] = {}
        if symbol:
            if not targets:
                symbol_targets = []
                for fs in file_structures:
                    for entity in fs.classes + fs.functions + fs.methods:
                        if entity.name == symbol or entity.name.endswith(f".{symbol}"):
                            symbol_targets.append(fs.relative_path.replace('\\', '/'))
                            break
                targets = sorted(list(set(symbol_targets)))
                if targets:
                    detection_source = "symbol"
            for t in targets:
                affected_symbols[t] = [symbol]

        # 4. Build ingress graph with extra known files (inject deleted & untracked targets)
        ingress_graph = self.build_ingress_graph(file_structures, extra_known_files=targets)

        # 5. Cycle-safe BFS impact traversal
        tier1_tests: List[str] = []
        direct_consumers_set: Set[str] = set()

        # Collect Tier 1 tests matching target names
        for t_name in self.find_tests_for_files(targets, all_file_paths):
            if t_name not in tier1_tests:
                tier1_tests.append(t_name)

        # Level 1: Direct consumers & direct test consumers
        for t in targets:
            consumers = ingress_graph.get(t, set())
            for c in consumers:
                if is_test_file(c):
                    if c not in tier1_tests:
                        tier1_tests.append(c)
                elif c not in targets:
                    direct_consumers_set.add(c)

        # Level 2+: Transitive consumers & Tier 2 tests
        tier2_tests: List[str] = []
        # Collect tests matching direct consumers
        for t_name in self.find_tests_for_files(list(direct_consumers_set), all_file_paths):
            if t_name not in tier1_tests and t_name not in tier2_tests:
                tier2_tests.append(t_name)

        transitive_consumers_set: Set[str] = set()
        visited: Set[str] = set(targets) | set(direct_consumers_set)
        queue: collections.deque = collections.deque((c, 1) for c in sorted(direct_consumers_set))

        while queue:
            curr, depth = queue.popleft()
            if depth >= max_depth:
                continue

            for next_cons in ingress_graph.get(curr, set()):
                if is_test_file(next_cons):
                    if next_cons not in tier1_tests and next_cons not in tier2_tests:
                        tier2_tests.append(next_cons)
                else:
                    if next_cons not in visited:
                        visited.add(next_cons)
                        transitive_consumers_set.add(next_cons)
                        queue.append((next_cons, depth + 1))

        # Order targeted tests (Tier 1 then Tier 2)
        targeted_tests: List[str] = []
        seen_tests: Set[str] = set()
        for t in tier1_tests + tier2_tests:
            if t not in seen_tests:
                seen_tests.add(t)
                targeted_tests.append(t)

        direct_consumers = sorted(list(direct_consumers_set))
        transitive_consumers = sorted(list(transitive_consumers_set))

        # 6. Test command synthesis & metrics computation
        rec_cmd = self.synthesize_test_command(targeted_tests)
        total_files = len(all_file_paths)
        direct_fan_out = len(direct_consumers)
        total_fan_out = len(direct_consumers) + len(transitive_consumers)
        fan_out_ratio = round((total_fan_out / total_files * 100.0), 2) if total_files > 0 else 0.0
        impact_level = compute_impact_level(total_fan_out, fan_out_ratio)

        return BlastRadiusReport(
            target_files=targets,
            impact_level=impact_level,
            direct_consumers=direct_consumers,
            transitive_consumers=transitive_consumers,
            targeted_tests=targeted_tests,
            recommended_test_command=rec_cmd,
            affected_symbols=affected_symbols,
            total_files=total_files,
            direct_fan_out=direct_fan_out,
            total_fan_out=total_fan_out,
            fan_out_ratio=fan_out_ratio,
            detection_source=detection_source
        )
