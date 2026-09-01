# PROJECT GENOME (2026-09-01T17:05:34Z) | hash:d0675c12d7

[ARCHITECTURE_DNA]
langs: Python(13)
modules: cli, src, tests
build_test: build=custom | test=unittest/pytest
metrics: 13 files, 2,286 lines

[DEPENDENCY_MATRIX]
external: cookiegli_core
hotspots: ast_scanner(fan_in:4), genome_engine(fan_in:2), cache_db(fan_in:1), darwin_memory(fan_in:1), monorepo_engine(fan_in:1)
src/cookiegli_core/cache_db.py -> ast_scanner
src/cookiegli_core/genome_engine.py -> ast_scanner
src/cookiegli_core/monorepo_engine.py -> ast_scanner, genome_engine
src/cookiegli_core/__init__.py -> ast_scanner, cache_db, darwin_memory, genome_engine

[API_REGISTRY]
classes:
  • class CodeEntity [src/cookiegli_core/ast_scanner.py:38]
  • class FileStructure [src/cookiegli_core/ast_scanner.py:47]
  • class AstScanner [methods: __init__, scan] [src/cookiegli_core/ast_scanner.py:60] - Multi-language structural scanner with m
  • class AstCache [methods: __init__, compute_sha256, get, put] [src/cookiegli_core/cache_db.py:17] - High-performance SQLite-backed AST cache
  • class LearnedArtifact [methods: smoothed_success_rate, record_use, apply_decay, apply_temporal_decay] [src/cookiegli_core/darwin_memory.py:24]
  • class DarwinMemory [methods: __init__, register, record_usage, get_active] [src/cookiegli_core/darwin_memory.py:86] - Enterprise Darwinian memory pool with at
  • class ArchitectureDNA [methods: to_compact] [src/cookiegli_core/genome_engine.py:28]
  • class DependencyMatrix [methods: to_compact] [src/cookiegli_core/genome_engine.py:60]
  • class ApiRegistry [methods: to_compact] [src/cookiegli_core/genome_engine.py:83]
  • class PatternStandards [methods: to_compact] [src/cookiegli_core/genome_engine.py:106]
functions:
  • def cmd_genome_build(args) [cli/cookiegli.py:32]
  • def cmd_genome_context(args) [cli/cookiegli.py:51]
  • def cmd_monorepo_build(args) [cli/cookiegli.py:63]
  • def cmd_monorepo_context(args) [cli/cookiegli.py:82]
  • def cmd_darwin(args) [cli/cookiegli.py:93]
  • def main() [cli/cookiegli.py:200]
  • def estimate_tokens(text: str) -> int [src/cookiegli_core/darwin_memory.py:17]

[PATTERN_STANDARDS]
conventions: snake_case-functions, PascalCase-classes, type-annotated

[EVOLUTION_HOTSPOTS]
recent_changes:
  • 6d05c75 fix(cli): synchronize CLI argument parsers with Darw
  • 79fcc0d feat(agents): update mandatory autonomous ruleset fo
  • c175388 feat(skills): upgrade cookiegli-core skill with ultr