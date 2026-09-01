# PROJECT GENOME (2026-09-01T16:11:37Z) | hash:5d3df24979

[ARCHITECTURE_DNA]
langs: Python(8)
modules: cli, src, tests
build_test: build=custom | test=unittest/pytest
metrics: 8 files, 1,439 lines

[DEPENDENCY_MATRIX]
external: cookiegli_core
hotspots: ast_scanner(fan_in:2), darwin_memory(fan_in:1), genome_engine(fan_in:1)
src/cookiegli_core/genome_engine.py -> ast_scanner
src/cookiegli_core/__init__.py -> ast_scanner, darwin_memory, genome_engine

[API_REGISTRY]
classes:
  • class CodeEntity [src/cookiegli_core/ast_scanner.py:37]
  • class FileStructure [src/cookiegli_core/ast_scanner.py:46]
  • class AstScanner [methods: __init__, scan] [src/cookiegli_core/ast_scanner.py:59] - Multi-language structural scanner with m
  • class LearnedArtifact [methods: smoothed_success_rate, record_use, apply_decay, to_summary_line] [src/cookiegli_core/darwin_memory.py:24]
  • class DarwinMemory [methods: __init__, register, record_usage, search] [src/cookiegli_core/darwin_memory.py:75] - Enterprise Darwinian memory pool with at
  • class ArchitectureDNA [methods: to_compact] [src/cookiegli_core/genome_engine.py:28]
  • class DependencyMatrix [methods: to_compact] [src/cookiegli_core/genome_engine.py:60]
  • class ApiRegistry [methods: to_compact] [src/cookiegli_core/genome_engine.py:83]
  • class PatternStandards [methods: to_compact] [src/cookiegli_core/genome_engine.py:106]
  • class EvolutionHotspots [methods: to_compact] [src/cookiegli_core/genome_engine.py:125]
functions:
  • def cmd_genome_build(args) [cli/cookiegli.py:20]
  • def cmd_genome_context(args) [cli/cookiegli.py:39]
  • def cmd_darwin(args) [cli/cookiegli.py:51]
  • def main() [cli/cookiegli.py:149]
  • def estimate_tokens(text: str) -> int [src/cookiegli_core/darwin_memory.py:17]
  • def estimate_tokens(text: str) -> int [src/cookiegli_core/genome_engine.py:20] - Accurate token estimate for code/markdow

[PATTERN_STANDARDS]
conventions: snake_case-functions, PascalCase-classes, type-annotated

[EVOLUTION_HOTSPOTS]
recent_changes:
  • 5ccc648 feat: CookieGli v2.0.0 â€” Enterprise context genome