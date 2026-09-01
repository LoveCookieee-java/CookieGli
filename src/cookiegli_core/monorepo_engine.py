"""
CookieGli Monorepo Engine — Multi-tier hierarchical genome generator for massive enterprise repositories (100k+ files).
Enables Tier 1 Root Cluster Mapping (<300 tokens) and Tier 2 Package Leaf Genomes (<500 tokens).
"""

import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .ast_scanner import AstScanner, FileStructure
from .genome_engine import GenomeEngine, ProjectGenome, estimate_tokens

IGNORED_DIRS = {
    'node_modules', '.git', '__pycache__', 'dist', 'build', '.next', 'target',
    'venv', '.venv', 'env', '.env', 'coverage', '.idea', '.vscode', 'vendor',
    'bin', 'obj', '.turbo', '.cache'
}

PACKAGE_INDICATORS = {
    'package.json': 'Node/JS/TS',
    'Cargo.toml': 'Rust',
    'go.mod': 'Go',
    'pom.xml': 'Java (Maven)',
    'build.gradle': 'Java/Kotlin (Gradle)',
    'pyproject.toml': 'Python',
    'setup.py': 'Python',
    'requirements.txt': 'Python',
    'CMakeLists.txt': 'C/C++',
}


@dataclass
class PackageNode:
    name: str
    rel_path: str
    abs_path: Path
    pkg_type: str
    files: List[FileStructure] = field(default_factory=list)
    internal_deps: Set[str] = field(default_factory=set)
    external_deps: Set[str] = field(default_factory=set)


@dataclass
class MonorepoGenome:
    root_path: str
    packages: Dict[str, PackageNode]
    inter_package_graph: Dict[str, Set[str]]
    total_files: int
    total_lines: int

    def to_root_compact(self, max_tokens: int = 400) -> str:
        """Generate Tier 1 Root Cluster Map (<300-400 tokens)."""
        lines = [
            f"# MONOREPO CLUSTER GENOME ({len(self.packages)} packages, {self.total_files:,} files, {self.total_lines:,} lines)",
            "",
            "[CLUSTER_DNA]",
            f"packages: {', '.join(sorted(self.packages.keys()))}",
            ""
        ]

        lines.append("[PACKAGE_TOPOLOGY]")
        for pkg_name, node in sorted(self.packages.items()):
            dep_str = f" -> {', '.join(sorted(node.internal_deps))}" if node.internal_deps else ""
            lines.append(f"• {pkg_name} [{node.pkg_type}, {len(node.files)} files, {node.rel_path or '.'}]{dep_str}")

        lines.append("")
        lines.append("[INTER_PACKAGE_DEPENDENCIES]")
        graph_entries = []
        for src, targets in sorted(self.inter_package_graph.items()):
            if targets:
                graph_entries.append(f"{src} ──► {', '.join(sorted(targets))}")

        if graph_entries:
            lines.extend(graph_entries)
        else:
            lines.append("no cross-package dependencies detected")

        raw_output = "\n".join(lines)
        return raw_output


class MonorepoEngine:
    """
    Enterprise Monorepo Coordinator.
    Detects package boundaries, builds hierarchical genomes, and provides multi-tier context slicing.
    """

    def __init__(self, root_path: str, max_files: int = 20000, use_cache: bool = True):
        self.root_path = Path(root_path).resolve()
        self.max_files = max_files
        self.use_cache = use_cache

    def discover_packages(self) -> Dict[str, PackageNode]:
        """Detect all package boundaries in the workspace."""
        packages: Dict[str, PackageNode] = {}

        # 1. Search for package indicators
        for current_dir, dirs, files in os.walk(self.root_path):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith('.')]

            cur_path = Path(current_dir)
            try:
                rel = cur_path.relative_to(self.root_path).as_posix()
            except ValueError:
                rel = ""

            for indicator, p_type in PACKAGE_INDICATORS.items():
                if indicator in files:
                    pkg_name = cur_path.name if rel and rel != '.' else 'root'
                    if pkg_name not in packages:
                        packages[pkg_name] = PackageNode(
                            name=pkg_name,
                            rel_path=rel if rel != '.' else '',
                            abs_path=cur_path,
                            pkg_type=p_type
                        )

        # Fallback if no indicators found: treat root as single package
        if not packages:
            packages['root'] = PackageNode(
                name='root',
                rel_path='',
                abs_path=self.root_path,
                pkg_type='Generic'
            )

        return packages

    def build(self) -> MonorepoGenome:
        """Scan codebase, assign files to packages, and resolve inter-package dependencies."""
        packages = self.discover_packages()
        scanner = AstScanner(str(self.root_path), max_files=self.max_files, use_cache=self.use_cache)
        all_files = scanner.scan()

        # Sort packages by path depth descending so nested packages take priority
        sorted_pkgs = sorted(packages.values(), key=lambda p: len(p.rel_path.split('/')) if p.rel_path else 0, reverse=True)

        for f in all_files:
            assigned = False
            for pkg in sorted_pkgs:
                if pkg.rel_path and f.path.startswith(pkg.rel_path + '/'):
                    pkg.files.append(f)
                    assigned = True
                    break
            if not assigned:
                # Assign to root package
                root_pkg = packages.get('root') or list(packages.values())[0]
                root_pkg.files.append(f)

        # Resolve inter-package dependency graph
        inter_graph: Dict[str, Set[str]] = defaultdict(set)
        pkg_names = set(packages.keys())

        for pkg_name, pkg in packages.items():
            for f in pkg.files:
                for imp in f.imports_external:
                    # check if external import matches another package name
                    clean_imp = imp.split('/')[0].replace('@', '')
                    for other_pkg in pkg_names:
                        if other_pkg != pkg_name and (clean_imp == other_pkg or clean_imp in other_pkg):
                            pkg.internal_deps.add(other_pkg)
                            inter_graph[pkg_name].add(other_pkg)

        total_files = len(all_files)
        total_lines = sum(f.total_lines for f in all_files)

        return MonorepoGenome(
            root_path=str(self.root_path),
            packages=packages,
            inter_package_graph=dict(inter_graph),
            total_files=total_files,
            total_lines=total_lines
        )

    def build_package_leaf_genome(self, package_name: str, max_tokens: int = 500) -> Optional[str]:
        """Build Tier 2 Leaf Genome for a specific package."""
        packages = self.discover_packages()
        if package_name not in packages:
            return None

        pkg = packages[package_name]
        engine = GenomeEngine(str(pkg.abs_path), use_cache=self.use_cache)
        genome = engine.build()
        return genome.to_compact(max_tokens)

    def synthesize_task_context(self, task: str, max_tokens: int = 1200) -> str:
        """
        Multi-Tier Context Synthesizer:
        1. Identifies relevant package from task.
        2. Generates Tier 1 Root Map + Tier 2 Package Genome + Targeted Entity AST.
        """
        monorepo_genome = self.build()
        root_map = monorepo_genome.to_root_compact(300)

        # Identify target package by keywords
        task_lower = task.lower()
        matched_pkg: Optional[PackageNode] = None

        for pkg_name, pkg in monorepo_genome.packages.items():
            if pkg_name.lower() in task_lower:
                matched_pkg = pkg
                break

        if not matched_pkg and monorepo_genome.packages:
            # Fallback to root or largest package
            matched_pkg = monorepo_genome.packages.get('root') or list(monorepo_genome.packages.values())[0]

        # Build leaf package context
        pkg_engine = GenomeEngine(str(matched_pkg.abs_path), use_cache=self.use_cache)
        pkg_genome = pkg_engine.build()
        pkg_slice = pkg_genome.synthesize_task_context(task, max_tokens=max_tokens - estimate_tokens(root_map) - 50)

        result = f"{root_map}\n\n[ACTIVE_PACKAGE_SLICE: {matched_pkg.name}]\n{pkg_slice}"
        return result
