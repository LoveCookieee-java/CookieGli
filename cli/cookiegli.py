#!/usr/bin/env python3
"""
CookieGli Unified Enterprise CLI — High-density context genome compressor, Monorepo hierarchy, and Bayesian ROI Darwin memory.
Zero 3rd-party dependencies. 100% Cross-platform (Windows / Linux / macOS).
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure UTF-8 output streams on Windows
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add src to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))

from cookiegli_core import (
    AstScanner,
    AstCache,
    GenomeEngine,
    MonorepoEngine,
    DarwinMemory,
    TargetManager,
    CookieGliMcpServer,
    CodeSkeletonizer,
    SkeletonResult,
    BlastRadiusEngine,
    BlastRadiusReport,
    BoostEngine,
    ErrorDistiller,
    DistilledError,
    DistilledLesson,
    clean_darwin_summary,
    estimate_tokens,
)
from cookiegli_core.distiller import resolve_darwin_state_path


def cmd_boost(args):
    target_path = Path(args.path or '.').resolve()
    with BoostEngine(str(target_path)) as boost_engine:
        if args.init:
            res = boost_engine.init_project(target=args.target, max_tokens=args.max_tokens)
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                print(f"[BOOST INIT] Scanned {res['total_files']} files | genome hash: {res['genome_hash']}")
                print(f"[BOOST INIT] Populated AST cache & FTS5 full-text index")
                for tgt, paths in res['synced_targets'].items():
                    print(f"  • {tgt}: {', '.join(paths)}")
                print("\n[BOOST INIT] Layer 1 static architectural anchor synced successfully.")
            return 0

        if not args.task:
            print("[ERROR] Missing required task description for boost. Use --init to initialize, or provide a task description.")
            return 1

        context_slice = boost_engine.synthesize_task_context(args.task, max_tokens=args.max_tokens)
        tokens = estimate_tokens(context_slice)

        if args.json:
            print(json.dumps({
                "task": args.task,
                "tokens": tokens,
                "max_tokens": args.max_tokens,
                "context": context_slice
            }, indent=2))
        else:
            print(f"[COOKIEGLI BOOST] Synthesized Layer 2 Dynamic Task Tail (~{tokens} tokens, limit: {args.max_tokens})\n")
            print(context_slice)

        return 0


def cmd_search(args):
    root_path = Path(getattr(args, 'root', None) or '.').resolve()
    cache_dir = root_path / '.cookiegli'
    with AstCache(str(cache_dir)) as cache:
        results = cache.search_bm25(args.query, limit=args.limit)

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    if not results:
        print(f"No symbols found matching query: '{args.query}'")
        return 0

    print(f"[FTS5 BM25 SEARCH] Found {len(results)} matching symbols for: '{args.query}'\n")
    for r in results:
        score_str = f" [bm25: {r['score']}]" if 'score' in r else ""
        sig_str = f" : {r['signature']}" if r.get('signature') else ""
        print(f"  • [{r['entity_type']}] {r['name']} ({r['relative_path']}:{r['line_number']}){sig_str}{score_str}")

    return 0


def cmd_genome_build(args):
    target_path = Path(args.path or '.').resolve()
    engine = GenomeEngine(str(target_path), use_cache=not args.no_cache)
    genome = engine.build()
    compact = genome.to_compact(args.max_tokens)
    tokens = estimate_tokens(compact)

    print(f"[GENOME BUILD] Generated {tokens} tokens (limit: {args.max_tokens}) | hash: {genome.genome_hash}\n")
    print(compact)

    if args.save:
        save_path = Path(args.save).resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(compact, encoding='utf-8')
        print(f"\n[SAVED] Wrote genome to: {save_path}")

    return 0


def cmd_genome_context(args):
    target_path = Path(args.path or '.').resolve()
    engine = GenomeEngine(str(target_path), use_cache=not args.no_cache)
    genome = engine.build()
    slice_context = genome.synthesize_task_context(args.task, args.max_tokens)
    tokens = estimate_tokens(slice_context)

    print(f"[GENOME CONTEXT] Synthesized ~{tokens} tokens for task: '{args.task}'\n")
    print(slice_context)
    return 0


def cmd_monorepo_build(args):
    target_path = Path(args.path or '.').resolve()
    engine = MonorepoEngine(str(target_path), max_files=args.max_files, use_cache=not args.no_cache)
    monorepo_genome = engine.build()
    root_compact = monorepo_genome.to_root_compact(args.max_tokens)
    tokens = estimate_tokens(root_compact)

    print(f"[MONOREPO BUILD] Detected {len(monorepo_genome.packages)} packages across {monorepo_genome.total_files:,} files | ~{tokens} tokens\n")
    print(root_compact)

    if args.save:
        save_path = Path(args.save).resolve()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(root_compact, encoding='utf-8')
        print(f"\n[SAVED] Wrote root cluster genome to: {save_path}")

    return 0


def cmd_monorepo_context(args):
    target_path = Path(args.path or '.').resolve()
    engine = MonorepoEngine(str(target_path), max_files=args.max_files, use_cache=not args.no_cache)
    slice_context = engine.synthesize_task_context(args.task, args.max_tokens)
    tokens = estimate_tokens(slice_context)

    print(f"[MONOREPO CONTEXT] Synthesized multi-tier context ~{tokens} tokens for task: '{args.task}'\n")
    print(slice_context)
    return 0


def cmd_darwin(args):
    root_path = Path(getattr(args, 'root', None) or os.getcwd()).resolve()
    state_file = getattr(args, 'state', None)
    if not state_file:
        state_file = str(resolve_darwin_state_path(root_path))
    multi_dir = getattr(args, 'multi_dir', None)
    memory = DarwinMemory(state_file=state_file, multi_file_dir=multi_dir)


    if args.action == 'register':
        content = args.content
        if args.file:
            content = Path(args.file).read_text(encoding='utf-8')
        if not content and not sys.stdin.isatty():
            content = sys.stdin.read()
        if not content:
            print("error: provide content via argument, --file, or stdin", file=sys.stderr)
            return 1
        tags = [t.strip() for t in args.tags.split(',')] if getattr(args, 'tags', None) else []
        scope = getattr(args, 'scope', 'global') or 'global'
        artifact = memory.register(args.name, args.type, content, scope=scope, tags=tags)
        print(json.dumps({
            'status': 'registered',
            'id': artifact.id,
            'name': artifact.name,
            'type': artifact.artifact_type,
            'scope': artifact.scope,
            'roi': round(artifact.roi, 3),
            'tags': artifact.tags
        }, indent=2))

    elif args.action == 'use':
        success = args.success.lower() in ('true', '1', 'yes')
        artifact = memory.record_usage(args.artifact_id, success)
        if not artifact:
            print(f"error: artifact {args.artifact_id} not found or pruned", file=sys.stderr)
            return 1
        print(json.dumps({
            'status': 'recorded',
            'id': artifact.id,
            'roi': round(artifact.roi, 3),
            'uses': artifact.use_count,
            'smoothed_sr': f"{artifact.smoothed_success_rate:.0%}"
        }, indent=2))

    elif args.action == 'search':
        tags = [t.strip() for t in args.tags.split(',')] if getattr(args, 'tags', None) else None
        scope = getattr(args, 'scope', None)
        results = memory.search(query=args.query or "", scope=scope, tags=tags)
        output = [{
            'id': a.id,
            'name': a.name,
            'type': a.artifact_type,
            'scope': a.scope,
            'roi': round(a.roi, 3),
            'uses': a.use_count,
            'tags': a.tags,
            'content': a.content[:80]
        } for a in results]
        print(json.dumps(output, indent=2, ensure_ascii=False))

    elif args.action == 'evolve':
        res = memory.evolve(
            roi_threshold=args.threshold,
            max_artifacts=args.max_capacity,
            decay_rate=args.decay,
            half_life_days=args.half_life
        )
        print(json.dumps(res, indent=2))

    elif args.action == 'list':
        scope = getattr(args, 'scope', None)
        active = memory.get_active(args.type, scope=scope)
        output = [{
            'id': a.id,
            'name': a.name,
            'type': a.artifact_type,
            'scope': a.scope,
            'roi': round(a.roi, 3),
            'uses': a.use_count,
            'smoothed_sr': f"{a.smoothed_success_rate:.0%}",
            'tags': a.tags,
            'content': a.content[:60]
        } for a in active]
        print(json.dumps(output, indent=2, ensure_ascii=False))

    elif args.action == 'sync':
        scope = getattr(args, 'scope', None)
        summary = memory.to_markdown_summary(args.max_tokens, scope=scope)
        TargetManager.sync_antigravity(root_path, darwin_text=summary)
        print(f"[SYNC] Synchronized Darwin learnings to Antigravity ruleset in {root_path / '.agents' / 'AGENTS.md'}")

    return 0


def cmd_sync(args):
    root_path = Path(args.root or '.').resolve()
    genome_text = None
    darwin_text = None

    if not args.no_genome:
        engine = GenomeEngine(str(root_path), use_cache=not args.no_cache)
        genome = engine.build()
        genome_text = genome.to_compact(args.max_genome_tokens)

    if not args.no_darwin:
        st = args.state
        if not st:
            st = str(resolve_darwin_state_path(root_path))
        darwin = DarwinMemory(state_file=st, multi_file_dir=args.multi_dir)
        darwin_text = clean_darwin_summary(darwin.to_markdown_summary(max_tokens=args.max_darwin_tokens))

    res = TargetManager.sync(args.target, root_path, genome_text=genome_text, darwin_text=darwin_text)
    print(f"[SYNC COMPLETED] Target: {args.target}")
    for target_name, files in res.items():
        print(f"  • {target_name.upper()}:")
        for f in files:
            print(f"    - {f}")
    return 0


def cmd_symbol(args):
    root_path = Path(args.root or '.').resolve()
    cache_dir = root_path / '.cookiegli'

    query = args.query or ''
    with AstCache(str(cache_dir)) as cache:
        results = cache.find_symbols(
            query=query,
            entity_type=args.type,
            exact=args.exact,
            limit=args.limit,
            path=args.path
        )

        if not results and cache.count() == 0:
            with AstScanner(str(root_path), use_cache=True, cache_dir=str(cache_dir)) as scanner:
                scanner.scan()
            results = cache.find_symbols(
                query=query,
                entity_type=args.type,
                exact=args.exact,
                limit=args.limit,
                path=args.path
            )

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0

    if not results:
        q_str = f" matching '{query}'" if query else ""
        print(f"No symbols found{q_str}.")
        return 0

    q_str = f" for query '{query}'" if query else ""
    print(f"[SYMBOL SEARCH] Found {len(results)} symbol(s){q_str}:\n")
    for r in results:
        sig = f" : {r['signature']}" if r.get('signature') else ""
        print(f"  • [{r['entity_type']}] {r['name']} ({r['relative_path']}:{r['line_number']}){sig}")
    return 0


def cmd_skeleton(args):
    file_path = Path(args.file_path).resolve()
    if not file_path.is_file():
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        return 1

    # Detect workspace root
    root = file_path.parent
    found_root = False
    while root.parent != root:
        if (root / '.cookiegli').exists() or (root / '.git').exists():
            found_root = True
            break
        root = root.parent
    if not found_root:
        root = Path.cwd()

    with CodeSkeletonizer(str(root), use_cache=not args.no_cache) as skel:
        result = skel.skeletonize_file(
            file_path,
            focus_symbol=args.focus,
            max_tokens=args.max_tokens,
        )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return 0

    header = f"[SKELETON] {result.file_path} ({result.language}) | ~{result.tokens} tokens (Tier {result.applied_tier})"
    if result.focus_symbol:
        header += f" | Focus: {result.focus_symbol}"
    if result.warning:
        header += f" | Warning: {result.warning}"
    print(header + "\n")
    print(result.skeleton)
    return 0


def cmd_blast(args):
    root_path = Path(args.path or '.').resolve()
    target_files = [args.file] if args.file else None

    with BlastRadiusEngine(str(root_path), use_cache=not args.no_cache) as engine:
        report = engine.analyze(
            target_files=target_files,
            symbol=args.symbol,
            max_depth=args.max_depth,
        )

    if args.json:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return 0

    compact = report.to_compact()
    print(compact)
    return 0


def cmd_mcp(args):
    root_path = Path(args.root or '.').resolve()
    server = CookieGliMcpServer(workspace_root=root_path)
    server.run_stdio()
    return 0


def cmd_distill(args):
    root_path = Path(getattr(args, 'root', None) or os.getcwd()).resolve()
    state_file = getattr(args, 'state', None)
    if not state_file:
        state_file = str(resolve_darwin_state_path(root_path))

    # Determine input log/traceback text
    log_text = getattr(args, 'traceback', None)
    if not log_text and getattr(args, 'file', None):
        f = Path(args.file)
        if not f.exists():
            print(f"error: file not found '{args.file}'", file=sys.stderr)
            return 1
        log_text = f.read_text(encoding='utf-8')
    if not log_text and not sys.stdin.isatty():
        log_text = sys.stdin.read()

    if not log_text:
        print("error: provide traceback/log via --traceback, --file, or stdin", file=sys.stderr)
        return 1

    diff_text = getattr(args, 'diff', None)
    if not diff_text and getattr(args, 'diff_file', None):
        df = Path(args.diff_file)
        if not df.exists():
            print(f"error: diff file not found '{args.diff_file}'", file=sys.stderr)
            return 1
        diff_text = df.read_text(encoding='utf-8')

    fix_desc = getattr(args, 'fix', None)
    scope_override = getattr(args, 'scope', None)
    sync_targets = getattr(args, 'sync', None)
    auto_register = getattr(args, 'auto_register', False) or (sync_targets is not None)

    distiller = ErrorDistiller(workspace_root=root_path, state_file=state_file)
    error, lesson, artifact = distiller.distill(
        log_text=log_text,
        diff_text=diff_text,
        fix_description=fix_desc,
        auto_register=auto_register,
        sync_targets=sync_targets,
        scope=scope_override
    )

    if getattr(args, 'json', False):
        output = {
            'error': {
                'type': error.error_type,
                'message': error.error_message,
                'runner': error.runner,
                'root_cause': f"{error.root_cause_frame.file}:{error.root_cause_frame.line}" if error.root_cause_frame else None,
                'frames_count': len(error.frames),
                'chained_count': len(error.chained_errors)
            },
            'lesson': {
                'name': lesson.name,
                'scope': lesson.scope,
                'content': lesson.content,
                'roi': round(lesson.roi, 3),
                'success_rate': f"{lesson.success_rate:.0%}",
                'tags': lesson.tags
            },
            'registered': {
                'id': artifact.id,
                'name': artifact.name,
                'roi': round(artifact.roi, 3),
                'uses': artifact.use_count,
                'pruned': artifact.pruned
            } if artifact else None,
            'synced': sync_targets if sync_targets else None
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("🧬 COOKIEGLI ERROR & TRACEBACK DISTILLER")
        print("=" * 60)
        print(f"• Runner Detected : {error.runner.upper()}")
        print(f"• Error Type      : {error.error_type}")
        print(f"• Error Message   : {error.error_message}")
        if error.root_cause_frame:
            rc = error.root_cause_frame
            func_str = f" in {rc.function}()" if rc.function else ""
            print(f"• Root Cause Frame: {rc.file}:{rc.line}{func_str}")
        if error.chained_errors:
            print(f"• Chained Causes  : {len(error.chained_errors)} preceding exceptions")
        print("-" * 60)
        print("🧠 SYNTHESIZED DARWIN LESSON")
        print("-" * 60)
        print(f"• Name            : {lesson.name}")
        print(f"• Scope           : [{lesson.scope}]")
        print(f"• Bayesian Prior  : ROI {lesson.roi:.2f} | SR {lesson.success_rate:.0%}")
        print(f"• Actionable Rule : {lesson.content}")
        if artifact:
            print("-" * 60)
            print(f"✓ Registered in Darwin Memory [ID: {artifact.id}] (Active: {not artifact.pruned})")
        if sync_targets:
            print(f"✓ Synchronized to AI Agent Target: {sync_targets}")
        print("=" * 60)

    return 0


def main():
    parser = argparse.ArgumentParser(prog='cookiegli', description="CookieGli Context Genome & Darwin Memory Toolkit")
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Genome parser
    p_genome = subparsers.add_parser('genome', help="Codebase genome compression commands")
    g_subs = p_genome.add_subparsers(dest='action', required=True)

    g_build = g_subs.add_parser('build', help="Build project genome")
    g_build.add_argument('path', nargs='?', default='.', help="Target project root directory")
    g_build.add_argument('--max-tokens', type=int, default=1500, help="Maximum genome token budget")
    g_build.add_argument('--save', default='.agents/GENOME.md', help="Save genome markdown path")
    g_build.add_argument('--no-cache', action='store_true', help="Disable SQLite incremental cache")
    g_build.set_defaults(func=cmd_genome_build)

    g_ctx = g_subs.add_parser('context', help="Synthesize task-relevant context")
    g_ctx.add_argument('task', help="Task description")
    g_ctx.add_argument('path', nargs='?', default='.', help="Target project root directory")
    g_ctx.add_argument('--max-tokens', type=int, default=1200, help="Maximum synthesized context tokens")
    g_ctx.add_argument('--no-cache', action='store_true', help="Disable SQLite incremental cache")
    g_ctx.set_defaults(func=cmd_genome_context)

    # Monorepo parser
    p_mono = subparsers.add_parser('monorepo', help="Hierarchical monorepo enterprise genome commands")
    m_subs = p_mono.add_subparsers(dest='action', required=True)

    m_build = m_subs.add_parser('build', help="Build Tier-1 root monorepo cluster genome")
    m_build.add_argument('path', nargs='?', default='.', help="Monorepo root directory")
    m_build.add_argument('--max-tokens', type=int, default=400, help="Maximum root genome token budget")
    m_build.add_argument('--max-files', type=int, default=20000, help="Maximum files to scan across monorepo")
    m_build.add_argument('--save', default='.agents/GENOME.md', help="Save path for root genome")
    m_build.add_argument('--no-cache', action='store_true', help="Disable SQLite incremental cache")
    m_build.set_defaults(func=cmd_monorepo_build)

    m_ctx = m_subs.add_parser('context', help="Synthesize multi-tier context across monorepo packages")
    m_ctx.add_argument('task', help="Task description")
    m_ctx.add_argument('path', nargs='?', default='.', help="Monorepo root directory")
    m_ctx.add_argument('--max-tokens', type=int, default=1200, help="Maximum tokens for combined context slice")
    m_ctx.add_argument('--max-files', type=int, default=20000, help="Maximum files to scan")
    m_ctx.add_argument('--no-cache', action='store_true', help="Disable SQLite incremental cache")
    m_ctx.set_defaults(func=cmd_monorepo_context)

    # Darwin parser
    p_darwin = subparsers.add_parser('darwin', help="Darwin ROI-based memory evolution commands")
    d_subs = p_darwin.add_subparsers(dest='action', required=True)

    # register
    d_reg = d_subs.add_parser('register', help="Register a learned artifact")
    d_reg.add_argument('name', help="Artifact name")
    d_reg.add_argument('type', choices=['pattern', 'lesson', 'skill', 'tool'], help="Artifact type")
    d_reg.add_argument('content', nargs='?', default='', help="Content / lesson")
    d_reg.add_argument('--scope', default='global', help="Domain scope / namespace (e.g. backend.auth)")
    d_reg.add_argument('--tags', help="Comma-separated tags (e.g. auth,security,db)")
    d_reg.add_argument('--file', help="Read content from file")
    d_reg.add_argument('--state', help="State JSON file path")
    d_reg.add_argument('--multi-dir', help="Multi-file storage directory")
    d_reg.set_defaults(func=cmd_darwin)

    # use
    d_use = d_subs.add_parser('use', help="Record usage of an artifact")
    d_use.add_argument('artifact_id', help="Target artifact ID")
    d_use.add_argument('success', nargs='?', default='true', choices=['true', 'false', 'True', 'False', '1', '0'], help="Usage outcome (true/false)")
    d_use.add_argument('--state', help="State JSON file path")
    d_use.add_argument('--multi-dir', help="Multi-file storage directory")
    d_use.set_defaults(func=cmd_darwin)

    # search
    d_search = d_subs.add_parser('search', help="Search active artifacts")
    d_search.add_argument('--query', default='', help="Search query string")
    d_search.add_argument('--scope', help="Domain namespace filter")
    d_search.add_argument('--tags', help="Comma-separated tags")
    d_search.add_argument('--state', help="State JSON file path")
    d_search.add_argument('--multi-dir', help="Multi-file storage directory")
    d_search.set_defaults(func=cmd_darwin)

    # list
    d_list = d_subs.add_parser('list', help="List active artifacts")
    d_list.add_argument('type', nargs='?', choices=['pattern', 'lesson', 'skill', 'tool'], help="Artifact type filter")
    d_list.add_argument('--scope', help="Domain namespace filter")
    d_list.add_argument('--state', help="State JSON file path")
    d_list.add_argument('--multi-dir', help="Multi-file storage directory")
    d_list.set_defaults(func=cmd_darwin)

    # evolve
    d_evolve = d_subs.add_parser('evolve', help="Evolve memory pool (decay and prune)")
    d_evolve.add_argument('--threshold', type=float, default=0.3, help="ROI prune threshold")
    d_evolve.add_argument('--max-capacity', type=int, default=50, help="Max active capacity")
    d_evolve.add_argument('--decay', type=float, default=0.95, help="Generational decay rate")
    d_evolve.add_argument('--half-life', type=float, default=None, help="Temporal half-life decay in days (e.g. 30)")
    d_evolve.add_argument('--state', help="State JSON file path")
    d_evolve.add_argument('--multi-dir', help="Multi-file storage directory")
    d_evolve.set_defaults(func=cmd_darwin)

    # sync
    d_sync = d_subs.add_parser('sync', help="Sync Darwin memory to .agents/AGENTS.md")
    d_sync.add_argument('--agents-file', help="Path to AGENTS.md")
    d_sync.add_argument('--scope', help="Sync only specific domain scope")
    d_sync.add_argument('--max-tokens', type=int, default=500, help="Max token budget")
    d_sync.add_argument('--state', help="State JSON file path")
    d_sync.add_argument('--multi-dir', help="Multi-file storage directory")
    d_sync.set_defaults(func=cmd_darwin)

    # Universal Target Sync parser
    p_sync = subparsers.add_parser('sync', help="Synchronize Genome and Darwin memory across AI agent formats")
    p_sync.add_argument('--target', choices=['claude', 'codex', 'antigravity', 'cursor', 'windsurf', 'all'], default='all', help="Target platform to sync")
    p_sync.add_argument('--root', default='.', help="Target project root directory")
    p_sync.add_argument('--max-genome-tokens', type=int, default=1500, help="Max token budget for Genome")
    p_sync.add_argument('--max-darwin-tokens', type=int, default=500, help="Max token budget for Darwin")
    p_sync.add_argument('--no-genome', action='store_true', help="Skip Genome synchronization")
    p_sync.add_argument('--no-darwin', action='store_true', help="Skip Darwin memory synchronization")
    p_sync.add_argument('--no-cache', action='store_true', help="Disable SQLite incremental cache")
    p_sync.add_argument('--state', help="Darwin state JSON file path")
    p_sync.add_argument('--multi-dir', help="Darwin multi-file storage directory")
    p_sync.set_defaults(func=cmd_sync)

    # Universal MCP Server parser
    p_mcp = subparsers.add_parser('mcp', help="Run pure Python stdlib MCP server over STDIO")
    p_mcp.add_argument('--root', default='.', help="Workspace root directory")
    p_mcp.set_defaults(func=cmd_mcp)

    # Symbol index search parser
    p_sym = subparsers.add_parser('symbol', help="Fast B-Tree symbol index search")
    p_sym.add_argument('query', nargs='?', default='', help="Symbol name or substring")
    p_sym.add_argument('--type', choices=['class', 'function', 'method', 'interface', 'struct', 'arrow_function'], help="Filter by entity type")
    p_sym.add_argument('--exact', action='store_true', help="Exact name match")
    p_sym.add_argument('--limit', type=int, default=50, help="Maximum results to return")
    p_sym.add_argument('--path', help="Filter by file path")
    p_sym.add_argument('--root', default='.', help="Project root directory")
    p_sym.add_argument('--json', action='store_true', help="Output results as JSON")
    p_sym.set_defaults(func=cmd_symbol)

    # Skeleton parser
    p_skel = subparsers.add_parser('skeleton', help="Generate compact code skeleton with optional focus symbol")
    p_skel.add_argument('file_path', help="Target source file path")
    p_skel.add_argument('--focus', help="Focus symbol to preserve verbatim (e.g. func_name or Class.method)")
    p_skel.add_argument('--max-tokens', type=int, default=600, help="Maximum skeleton token budget")
    p_skel.add_argument('--json', action='store_true', help="Output skeleton result as JSON")
    p_skel.add_argument('--no-cache', action='store_true', help="Disable SQLite incremental cache")
    p_skel.set_defaults(func=cmd_skeleton)

    # Blast radius parser
    p_blast = subparsers.add_parser('blast', help="Analyze Git blast radius and downstream dependency impact")
    p_blast.add_argument('--diff', action='store_true', help="Detect changed files via git status or mtime fallback")
    p_blast.add_argument('--symbol', help="Specific symbol to analyze")
    p_blast.add_argument('--file', help="Specific target file to analyze")
    p_blast.add_argument('--path', default='.', help="Target project root directory")
    p_blast.add_argument('--max-depth', type=int, default=3, help="Maximum BFS traversal depth (default: 3)")
    p_blast.add_argument('--json', action='store_true', help="Output results as JSON")
    p_blast.add_argument('--no-cache', action='store_true', help="Disable SQLite incremental cache")
    p_blast.set_defaults(func=cmd_blast)

    # Distill parser
    p_distill = subparsers.add_parser('distill', help="Distill test failures, panics, or tracebacks into actionable Darwin learnings")
    p_distill.add_argument('--traceback', '-t', help="Traceback or test failure log string")
    p_distill.add_argument('--file', '-f', help="File containing traceback or test log")
    p_distill.add_argument('--diff', '-d', help="Git diff or code patch showing the fix")
    p_distill.add_argument('--diff-file', help="File containing git diff or code patch")
    p_distill.add_argument('--fix', help="Human-provided explanation of the fix")
    p_distill.add_argument('--auto-register', action='store_true', help="Automatically register lesson into Darwin memory pool")
    p_distill.add_argument('--sync', nargs='?', const='all', default=None, help="Sync registered learnings to AI agent targets (default: all)")
    p_distill.add_argument('--scope', help="Override domain scope namespace")
    p_distill.add_argument('--state', help="Explicit path to darwin_state.json")
    p_distill.add_argument('--root', default='.', help="Project root directory")
    p_distill.add_argument('--json', action='store_true', help="Output results as JSON")
    p_distill.set_defaults(func=cmd_distill)

    # Boost parser
    p_boost = subparsers.add_parser('boost', aliases=['bootstrap'], help="Two-tier boost: Layer 1 static anchor (--init) or Layer 2 dynamic task tail")
    p_boost.add_argument('task', nargs='?', default='', help="Specific programming or debugging task description")
    p_boost.add_argument('--init', action='store_true', help="One-command init: scan AST, populate B-Tree & FTS5, and sync Layer 1 static anchor")
    p_boost.add_argument('--max-tokens', type=int, default=600, help="Maximum token budget for Layer 2 dynamic task context (default: 600)")
    p_boost.add_argument('--path', default='.', help="Target project root directory")
    p_boost.add_argument('--target', choices=['claude', 'codex', 'antigravity', 'cursor', 'windsurf', 'all'], default='all', help="Target platform to sync when --init is used")
    p_boost.add_argument('--json', action='store_true', help="Output results as JSON")
    p_boost.set_defaults(func=cmd_boost)

    # Search parser
    p_search = subparsers.add_parser('search', help="Full-text symbol search using SQLite FTS5 BM25+ ranking")
    p_search.add_argument('query', help="Symbol name or search terms")
    p_search.add_argument('--limit', type=int, default=20, help="Maximum results to return (default: 20)")
    p_search.add_argument('--root', default='.', help="Project root directory")
    p_search.add_argument('--json', action='store_true', help="Output results as JSON")
    p_search.set_defaults(func=cmd_search)

    args = parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
