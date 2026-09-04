"""
Project Genome Engine — Compresses codebase architecture into a dense representation (<= 1500 tokens)
and synthesizes task-specific context on demand (<= 1200 tokens).
100% Cross-platform, zero third-party dependencies, enhanced with token semantic relevancy scoring.
"""

import datetime
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .ast_scanner import AstScanner, FileStructure, CodeEntity


def estimate_tokens(text: str) -> int:
    """Accurate token estimate for code/markdown (~3.8 chars per token)."""
    if not text:
        return 0
    return max(1, len(text) // 4)


@dataclass
class ArchitectureDNA:
    languages: Dict[str, int] = field(default_factory=dict)
    frameworks: List[str] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)
    modules: List[str] = field(default_factory=list)
    build_system: str = "custom"
    test_framework: str = "none"
    total_files: int = 0
    total_lines: int = 0

    def to_compact(self, max_tokens: int = 350) -> str:
        lines = ["[ARCHITECTURE_DNA]"]
        lang_str = ", ".join(f"{lang}({count})" for lang, count in sorted(self.languages.items(), key=lambda x: x[1], reverse=True)[:5])
        if lang_str:
            lines.append(f"langs: {lang_str}")
        if self.frameworks:
            lines.append(f"frameworks: {', '.join(self.frameworks[:5])}")
        if self.entry_points:
            lines.append(f"entry_points: {', '.join(self.entry_points[:5])}")
        if self.modules:
            lines.append(f"modules: {', '.join(self.modules[:8])}")
        lines.append(f"build_test: build={self.build_system} | test={self.test_framework}")
        lines.append(f"metrics: {self.total_files} files, {self.total_lines:,} lines")

        result = "\n".join(lines)
        while estimate_tokens(result) > max_tokens and len(lines) > 2:
            lines.pop()
            result = "\n".join(lines)
        return result


@dataclass
class DependencyMatrix:
    external_packages: List[str] = field(default_factory=list)
    internal_graph: Dict[str, List[str]] = field(default_factory=dict)
    hotspots: List[Tuple[str, int]] = field(default_factory=list)

    def to_compact(self, max_tokens: int = 350) -> str:
        lines = ["[DEPENDENCY_MATRIX]"]
        if self.external_packages:
            lines.append(f"external: {', '.join(self.external_packages[:15])}")
        if self.hotspots:
            lines.append(f"hotspots: {', '.join(f'{f}(fan_in:{c})' for f, c in self.hotspots[:5])}")
        for mod, deps in list(self.internal_graph.items())[:6]:
            if deps:
                lines.append(f"{mod} -> {', '.join(deps[:4])}")

        result = "\n".join(lines)
        while estimate_tokens(result) > max_tokens and len(lines) > 2:
            lines.pop()
            result = "\n".join(lines)
        return result


@dataclass
class ApiRegistry:
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)

    def to_compact(self, max_tokens: int = 400) -> str:
        lines = ["[API_REGISTRY]"]
        if self.classes:
            lines.append("classes:")
            for c in self.classes[:10]:
                lines.append(f"  • {c}")
        if self.functions:
            lines.append("functions:")
            for f in self.functions[:12]:
                lines.append(f"  • {f}")

        result = "\n".join(lines)
        while estimate_tokens(result) > max_tokens and len(lines) > 2:
            lines.pop()
            result = "\n".join(lines)
        return result


@dataclass
class PatternStandards:
    conventions: List[str] = field(default_factory=list)
    paradigms: List[str] = field(default_factory=list)

    def to_compact(self, max_tokens: int = 200) -> str:
        lines = ["[PATTERN_STANDARDS]"]
        if self.conventions:
            lines.append(f"conventions: {', '.join(self.conventions[:6])}")
        if self.paradigms:
            lines.append(f"paradigms: {', '.join(self.paradigms[:6])}")

        result = "\n".join(lines)
        while estimate_tokens(result) > max_tokens and len(lines) > 2:
            lines.pop()
            result = "\n".join(lines)
        return result


@dataclass
class EvolutionHotspots:
    recent_commits: List[str] = field(default_factory=list)
    todo_markers: List[str] = field(default_factory=list)

    def to_compact(self, max_tokens: int = 200, include_commits: bool = False) -> str:
        lines = ["[EVOLUTION_HOTSPOTS]"]
        if include_commits and self.recent_commits:
            lines.append("recent_changes:")
            for c in self.recent_commits[:3]:
                lines.append(f"  • {c[:60]}")
        if self.todo_markers:
            lines.append("open_todos:")
            for t in self.todo_markers[:3]:
                lines.append(f"  • {t[:60]}")
        if len(lines) == 1:
            lines.append("(clean / no pending hotspots)")

        result = "\n".join(lines)
        while estimate_tokens(result) > max_tokens and len(lines) > 2:
            lines.pop()
            result = "\n".join(lines)
        return result


@dataclass
class ProjectGenome:
    dna: ArchitectureDNA = field(default_factory=ArchitectureDNA)
    deps: DependencyMatrix = field(default_factory=DependencyMatrix)
    apis: ApiRegistry = field(default_factory=ApiRegistry)
    patterns: PatternStandards = field(default_factory=PatternStandards)
    evolution: EvolutionHotspots = field(default_factory=EvolutionHotspots)
    generated_at: str = ""
    genome_hash: str = ""

    def to_compact(self, max_tokens: int = 1500) -> str:
        blocks = [
            f"# PROJECT GENOME | id:{self.genome_hash}",
            self.dna.to_compact(350),
            self.deps.to_compact(350),
            self.apis.to_compact(400),
            self.patterns.to_compact(200),
            self.evolution.to_compact(200, include_commits=False),
        ]
        result = "\n\n".join(blocks)
        token_count = estimate_tokens(result)
        if token_count > max_tokens:
            ratio = max_tokens / token_count
            trimmed_blocks = [blocks[0]]
            for b in blocks[1:]:
                target_len = max(int(len(b) * ratio), 50)
                trimmed = b[:target_len]
                last_nl = trimmed.rfind('\n')
                if last_nl > 0:
                    trimmed = trimmed[:last_nl]
                trimmed_blocks.append(trimmed)
            result = "\n\n".join(trimmed_blocks)
        return result

    def synthesize_task_context(self, task: str, max_tokens: int = 1200) -> str:
        """Synthesize a task-specific context slice with keyword & entity relevance ranking."""
        task_words = set(re.findall(r'[a-zA-Z0-9_]+', task.lower()))

        # Prioritize matching classes and functions directly related to task terms
        matched_classes = [c for c in self.apis.classes if any(w in c.lower() for w in task_words if len(w) > 2)]
        matched_funcs = [f for f in self.apis.functions if any(w in f.lower() for w in task_words if len(w) > 2)]

        custom_api_lines = ["[API_REGISTRY_RELEVANT]"]
        if matched_classes or matched_funcs:
            if matched_classes:
                custom_api_lines.append("target_classes:")
                for c in matched_classes[:8]:
                    custom_api_lines.append(f"  • {c}")
            if matched_funcs:
                custom_api_lines.append("target_functions:")
                for f in matched_funcs[:10]:
                    custom_api_lines.append(f"  • {f}")
            api_slice = "\n".join(custom_api_lines)
        else:
            api_slice = self.apis.to_compact(350)

        # Keyword weights for structural blocks
        weights = {
            'dna': sum(1 for kw in ['setup', 'build', 'framework', 'config', 'install', 'init', 'architecture'] if kw in task_words) + 1,
            'deps': sum(1 for kw in ['import', 'package', 'module', 'dependency', 'require', 'library', 'hotspot'] if kw in task_words) + 1,
            'apis': 3 if (matched_classes or matched_funcs) else 1,
            'patterns': sum(1 for kw in ['pattern', 'refactor', 'style', 'convention', 'naming', 'format', 'async'] if kw in task_words) + 1,
            'evolution': sum(1 for kw in ['fix', 'bug', 'issue', 'todo', 'error', 'recent', 'regression'] if kw in task_words) + 1,
        }

        total_weight = sum(weights.values())
        budget_per_block = {
            'dna': max(int(max_tokens * (weights['dna'] / total_weight)), 80),
            'deps': max(int(max_tokens * (weights['deps'] / total_weight)), 80),
            'apis': max(int(max_tokens * (weights['apis'] / total_weight)), 120),
            'patterns': max(int(max_tokens * (weights['patterns'] / total_weight)), 60),
            'evolution': max(int(max_tokens * (weights['evolution'] / total_weight)), 60),
        }

        slices = [
            f"[SYNTHESIZED TASK CONTEXT | Task: {task[:80]}]",
            api_slice,
            self.dna.to_compact(budget_per_block['dna']),
            self.deps.to_compact(budget_per_block['deps']),
            self.patterns.to_compact(budget_per_block['patterns']),
            self.evolution.to_compact(budget_per_block['evolution'], include_commits=True),
        ]

        result = "\n\n".join(slices)
        if estimate_tokens(result) > max_tokens:
            result = result[:max_tokens * 4]
            last_nl = result.rfind('\n')
            if last_nl > 0:
                result = result[:last_nl]
        return result


class GenomeEngine:
    """Builds and manages Project Genome models."""

    FRAMEWORK_SIGNATURES = {
        'FastAPI': ['fastapi', 'APIRouter', 'FastAPI('],
        'Flask': ['flask', 'Flask(', 'render_template'],
        'Django': ['django', 'models.Model', 'urlpatterns'],
        'React': ['react', 'useState', 'useEffect', 'jsx'],
        'Express': ['express()', 'express', 'app.listen'],
        'Next.js': ['next', 'next/image', 'getServerSideProps'],
        'Pytest': ['pytest', '@pytest.fixture', 'pytest.mark'],
        'Unittest': ['unittest.TestCase', 'self.assertEqual'],
    }

    def __init__(self, root_path: str, use_cache: bool = True, cache_dir: Optional[str] = None):
        self.root_path = Path(root_path).resolve()
        self.use_cache = use_cache
        self.cache_dir = cache_dir
        self.scanner = AstScanner(str(self.root_path), use_cache=self.use_cache, cache_dir=self.cache_dir)

    def close(self) -> None:
        """Release underlying scanner and cache resources cleanly."""
        if hasattr(self, 'scanner') and self.scanner:
            try:
                self.scanner.close()
            except Exception:
                pass
            self.scanner = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def build(self) -> ProjectGenome:
        """Scan project and construct the full ProjectGenome."""
        files = self.scanner.scan()
        dna = self._build_dna(files)
        deps = self._build_deps(files)
        apis = self._build_apis(files)
        patterns = self._build_patterns(files)
        evolution = self._build_evolution()

        now_str = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        raw_content = f"{dna.to_compact()}{deps.to_compact()}{apis.to_compact()}"
        genome_hash = hashlib.sha256(raw_content.encode('utf-8')).hexdigest()[:10]

        return ProjectGenome(
            dna=dna,
            deps=deps,
            apis=apis,
            patterns=patterns,
            evolution=evolution,
            generated_at=now_str,
            genome_hash=genome_hash,
        )

    def _build_dna(self, files: List[FileStructure]) -> ArchitectureDNA:
        dna = ArchitectureDNA()
        dna.total_files = len(files)
        dna.total_lines = sum(f.total_lines for f in files)

        lang_counts: Dict[str, int] = {}
        for f in files:
            lang_counts[f.language] = lang_counts.get(f.language, 0) + 1
        dna.languages = lang_counts

        for f in files:
            if f.is_entry_point:
                dna.entry_points.append(f.relative_path)

        mods = set()
        for f in files:
            parts = Path(f.relative_path).parts
            if len(parts) > 1:
                mods.add(parts[0])
        dna.modules = sorted(mods)[:10]

        all_ext_imports = {pkg.lower() for f in files for pkg in f.imports_external}
        detected_fw = []
        for fw_name, sigs in self.FRAMEWORK_SIGNATURES.items():
            if any(sig.lower() in all_ext_imports for sig in sigs):
                detected_fw.append(fw_name)
        dna.frameworks = detected_fw

        if (self.root_path / 'pyproject.toml').exists() or (self.root_path / 'setup.py').exists():
            dna.build_system = 'python-pip/setuptools'
        elif (self.root_path / 'package.json').exists():
            dna.build_system = 'npm/yarn'
        elif (self.root_path / 'Cargo.toml').exists():
            dna.build_system = 'cargo'
        elif (self.root_path / 'go.mod').exists():
            dna.build_system = 'go-modules'

        if any('unittest' in f.relative_path.lower() or 'test_' in f.relative_path.lower() for f in files):
            dna.test_framework = 'unittest/pytest'

        return dna

    def _build_deps(self, files: List[FileStructure]) -> DependencyMatrix:
        matrix = DependencyMatrix()

        ext_set: Set[str] = set()
        for f in files:
            ext_set.update(f.imports_external)
        matrix.external_packages = sorted(ext_set)[:20]

        fan_in_counts: Dict[str, int] = {}
        for f in files:
            if f.imports_internal:
                matrix.internal_graph[f.relative_path] = f.imports_internal[:5]
                for imp in f.imports_internal:
                    fan_in_counts[imp] = fan_in_counts.get(imp, 0) + 1

        matrix.hotspots = sorted(fan_in_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        return matrix

    def _build_apis(self, files: List[FileStructure]) -> ApiRegistry:
        registry = ApiRegistry()

        for f in files:
            for cls in f.classes:
                doc = f" - {cls.docstring[:40]}" if cls.docstring else ""
                registry.classes.append(f"{cls.signature} [{f.relative_path}:{cls.line_number}]{doc}")
            for fn in f.functions:
                doc = f" - {fn.docstring[:40]}" if fn.docstring else ""
                registry.functions.append(f"{fn.signature} [{f.relative_path}:{fn.line_number}]{doc}")

        return registry

    def _build_patterns(self, files: List[FileStructure]) -> PatternStandards:
        patterns = PatternStandards()
        has_async = any('async def' in fn.signature for f in files for fn in f.functions)
        has_dataclass = any('dataclass' in cls.signature for f in files for cls in f.classes)

        if has_async:
            patterns.paradigms.append('async/await')
        if has_dataclass:
            patterns.paradigms.append('dataclasses-model')
        patterns.conventions.append('snake_case-functions')
        patterns.conventions.append('PascalCase-classes')
        patterns.conventions.append('type-annotated')
        return patterns

    def _build_evolution(self) -> EvolutionHotspots:
        evolution = EvolutionHotspots()

        try:
            res = subprocess.run(
                ['git', 'log', '--oneline', '-n', '5'],
                cwd=str(self.root_path),
                capture_output=True,
                text=True,
                timeout=3,
                check=False
            )
            if res.returncode == 0 and res.stdout:
                evolution.recent_commits = [line.strip() for line in res.stdout.splitlines() if line.strip()][:5]
        except Exception:
            pass

        todos = []
        todo_regex = re.compile(r'#\s*(TODO|FIXME|NOTE|BUG):\s*(.*)', re.IGNORECASE)
        for root, _, filenames in os.walk(self.root_path):
            for name in filenames:
                if name.endswith(('.py', '.js', '.ts', '.java', '.md')):
                    p = Path(root) / name
                    try:
                        content = p.read_text(encoding='utf-8', errors='ignore')
                        for line_no, line in enumerate(content.splitlines()[:200], start=1):
                            m = todo_regex.search(line)
                            if m:
                                rel = p.relative_to(self.root_path).as_posix()
                                todos.append(f"{rel}:{line_no} [{m.group(1).upper()}] {m.group(2).strip()}")
                                if len(todos) >= 5:
                                    break
                    except Exception:
                        pass
                if len(todos) >= 5:
                    break
            if len(todos) >= 5:
                break

        evolution.todo_markers = todos
        return evolution
