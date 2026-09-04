# PROJECT GENOME | id:07145c3cf9

[ARCHITECTURE_DNA]
langs: Python(27)
entry_points: src/cookiegli_core/mcp_server.py, tests/test_mcp_server.py
modules: cli, src, tests
build_test: build=custom | test=unittest/pytest

[DEPENDENCY_MATRIX]
external: cookiegli
hotspots: cookiegli_core.mcp_server(fan_in:7), ast_scanner(fan_in:6), cookiegli_core.ast_scanner(fan_in:6), genome_engine(fan_in:5), cookiegli_core.genome_engine(fan_in:5)
cli/cookiegli.py -> cookiegli_core, cookiegli_core.distiller
src/cookiegli_core/blast_radius.py -> ast_scanner, cache_db, genome_engine
src/cookiegli_core/boost_engine.py -> adapters, ast_scanner, blast_radius, cache_db
src/cookiegli_core/cache_db.py -> ast_scanner
src/cookiegli_core/distiller.py -> adapters, darwin_memory

[API_REGISTRY]
classes:
  • class TargetManager [methods: sync_claude, sync_codex, sync_antigravity, sync_cursor] [src/cookiegli_core/adapters.py:17] - Manages idempotent, bounded injection of
  • class CodeEntity [src/cookiegli_core/ast_scanner.py:38]
  • class FileStructure [src/cookiegli_core/ast_scanner.py:47]
  • class AstScanner [methods: __init__, close, scan] [src/cookiegli_core/ast_scanner.py:61] - Multi-language structural scanner with m
  • class BlastRadiusReport [methods: to_dict, to_compact] [src/cookiegli_core/blast_radius.py:66] - Comprehensive blast radius impact report
  • class BlastRadiusEngine [methods: __init__, close, detect_changed_files, build_ingress_graph] [src/cookiegli_core/blast_radius.py:239] - Git Blast Radius & Downstream Dependency
  • class BoostEngine [methods: __init__, close, init_project, synthesize_task_context] [src/cookiegli_core/boost_engine.py:59] - CookieGli Boost Engine for 2026 Frontier
  • class AstCache [methods: __init__, compute_sha256, get, put] [src/cookiegli_core/cache_db.py:18] - High-performance SQLite-backed AST cache
  • class LearnedArtifact [methods: smoothed_success_rate, record_use, apply_decay, apply_temporal_decay] [src/cookiegli_core/darwin_memory.py:24]
  • class DarwinMemory [methods: __init__, register, record_usage, get_active] [src/cookiegli_core/darwin_memory.py:87] - Enterprise Darwinian memory pool with at
functions:
  • def cmd_boost(args) [cli/cookiegli.py:51]

[PATTERN_STANDARDS]

[EVOLUTION_HOTSPOTS]
