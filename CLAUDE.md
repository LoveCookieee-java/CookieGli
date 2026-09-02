# Claude Code Project Instructions

## Architecture & Codebase Map
<!-- cookiegli:genome:start -->
### 🧬 Project AST Genome (<600 tokens)
```
# PROJECT GENOME (2026-09-02T16:46:19Z) | hash:9a859b4f18

[ARCHITECTURE_DNA]
langs: Python(17)
entry_points: src/cookiegli_core/mcp_server.py, tests/test_mcp_server.py
modules: cli, src, tests
build_test: build=custom | test=unittest/pytest
metrics: 17 files, 3,080 lines

[DEPENDENCY_MATRIX]
external: cookiegli_core
hotspots: ast_scanner(fan_in:4), genome_engine(fan_in:2), adapters(fan_in:1), cache_db(fan_in:1), darwin_memory(fan_in:1)
src/cookiegli_core/cache_db.py -> ast_scanner
src/cookiegli_core/genome_engine.py -> ast_scanner
src/cookiegli_core/monorepo_engine.py -> ast_scanner, genome_engine
src/cookiegli_core/__init__.py -> adapters, ast_scanner, cache_db, darwin_memory

[API_REGISTRY]
classes:
  • class TargetManager [methods: sync_claude, sync_codex, sync_antigravity, sync_cursor] [src/cookiegli_core/adapters.py:16] - Manages idempotent, bounded injection of
  • class CodeEntity [src/cookiegli_core/ast_scanner.py:38]
  • class FileStructure [src/cookiegli_core/ast_scanner.py:47]
  • class AstScanner [methods: __init__, scan] [src/cookiegli_core/ast_scanner.py:60] - Multi-language structural scanner with m
  • class AstCache [methods: __init__, compute_sha256, get, put] [src/cookiegli_core/cache_db.py:17] - High-performance SQLite-backed AST cache
  • class LearnedArtifact [methods: smoothed_success_rate, record_use, apply_decay, apply_temporal_decay] [src/cookiegli_core/darwin_memory.py:24]
  • class DarwinMemory [methods: __init__, register, record_usage, get_active] [src/cookiegli_core/darwin_memory.py:86] - Enterprise Darwinian memory pool with at
  • class ArchitectureDNA [methods: to_compact] [src/cookiegli_core/genome_engine.py:28]
  • class DependencyMatrix [methods: to_compact] [src/cookiegli_core/genome_engine.py:60]
  • class ApiRegistry [methods: to_compact] [src/cookiegli_core/genome_engine.py:83]
functions:
  • def cmd_genome_build(args) [cli/cookiegli.py:41]
  • def cmd_genome_context(args) [cli/cookiegli.py:60]
  • def cmd_monorepo_build(args) [cli/cookiegli.py:72]
  • def cmd_monorepo_context(args) [cli/cookiegli.py:91]
  • def cmd_darwin(args) [cli/cookiegli.py:102]
  • def cmd_sync(args) [cli/cookiegli.py:209]
  • def cmd_mcp(args) [cli/cookiegli.py:241]
  • def main() [cli/cookiegli.py:248]

[PATTERN_STANDARDS]
conventions: snake_case-functions, PascalCase-classes, type-annotated

[EVOLUTION_HOTSPOTS]
recent_changes:
  • 9329d75 docs: update CookieGli README for v2.2.0 universal s
  • f0ad687 feat(universal): add multi-target adapters and pure-
  • 1e9a9ea feat(agents): synchronize mandatory enterprise rules
```
<!-- cookiegli:genome:end -->

## Learned Engineering Patterns
<!-- cookiegli:darwin:start -->
### 🧬 Darwin Learned Best Practices
<!-- darwin:learnings:start -->
### 🧬 Darwin Learned Patterns & Best Practices
- *No verified patterns evolved yet. Run tasks to build evolutionary memory.*
<!-- darwin:learnings:end -->
<!-- cookiegli:darwin:end -->
