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
    estimate_tokens,
)


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
    state_file = getattr(args, 'state', None) or os.path.join(os.getcwd(), '.agents', '.darwin_state.json')
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
        agents_file = Path(args.agents_file or os.path.join(os.getcwd(), '.agents', 'AGENTS.md'))
        if agents_file.exists():
            text = agents_file.read_text(encoding='utf-8')
            if '<!-- darwin:learnings:start -->' in text and '<!-- darwin:learnings:end -->' in text:
                import re
                new_text = re.sub(
                    r'<!-- darwin:learnings:start -->.*?<!-- darwin:learnings:end -->',
                    summary,
                    text,
                    flags=re.DOTALL
                )
                agents_file.write_text(new_text, encoding='utf-8')
                print(f"[SYNC] Updated Darwin learnings in {agents_file}")
            else:
                agents_file.write_text(text + f"\n\n{summary}\n", encoding='utf-8')
                print(f"[SYNC] Appended Darwin learnings to {agents_file}")
        else:
            print(summary)

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
            default_st = root_path / ".cookiegli" / "darwin_state.json"
            if default_st.exists():
                st = str(default_st)
            else:
                agent_st = root_path / ".agents" / ".darwin_state.json"
                if agent_st.exists():
                    st = str(agent_st)
        darwin = DarwinMemory(state_file=st, multi_file_dir=args.multi_dir)
        darwin_text = darwin.to_markdown_summary(max_tokens=args.max_darwin_tokens)

    res = TargetManager.sync(args.target, root_path, genome_text=genome_text, darwin_text=darwin_text)
    print(f"[SYNC COMPLETED] Target: {args.target}")
    for target_name, files in res.items():
        print(f"  • {target_name.upper()}:")
        for f in files:
            print(f"    - {f}")
    return 0


def cmd_mcp(args):
    root_path = Path(args.root or '.').resolve()
    server = CookieGliMcpServer(workspace_root=root_path)
    server.run_stdio()
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

    args = parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
