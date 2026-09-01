#!/usr/bin/env python3
"""
CookieGli Unified CLI — High-density context genome compressor and Bayesian ROI Darwin memory.
Zero 3rd-party dependencies. 100% Cross-platform (Windows / Linux / macOS).
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add src to path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))

from cookiegli_core import AstScanner, GenomeEngine, DarwinMemory, estimate_tokens


def cmd_genome_build(args):
    target_path = Path(args.path or '.').resolve()
    engine = GenomeEngine(str(target_path))
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
    engine = GenomeEngine(str(target_path))
    genome = engine.build()
    slice_context = genome.synthesize_task_context(args.task, args.max_tokens)
    tokens = estimate_tokens(slice_context)

    print(f"[GENOME CONTEXT] Synthesized ~{tokens} tokens for task: '{args.task}'\n")
    print(slice_context)
    return 0


def cmd_darwin(args):
    state_file = args.state or os.path.join(os.getcwd(), '.agents', '.darwin_state.json')
    memory = DarwinMemory(state_file)

    if args.action == 'register':
        content = args.content
        if args.file:
            content = Path(args.file).read_text(encoding='utf-8')
        if not content and not sys.stdin.isatty():
            content = sys.stdin.read()
        if not content:
            print("error: provide content via argument, --file, or stdin", file=sys.stderr)
            return 1
        tags = [t.strip() for t in args.tags.split(',')] if args.tags else []
        artifact = memory.register(args.name, args.type, content, tags=tags)
        print(json.dumps({
            'status': 'registered',
            'id': artifact.id,
            'name': artifact.name,
            'type': artifact.artifact_type,
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
        tags = [t.strip() for t in args.tags.split(',')] if args.tags else None
        results = memory.search(query=args.query or "", tags=tags)
        output = [{
            'id': a.id,
            'name': a.name,
            'type': a.artifact_type,
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
            decay_rate=args.decay
        )
        print(json.dumps(res, indent=2))

    elif args.action == 'list':
        active = memory.get_active(args.type)
        output = [{
            'id': a.id,
            'name': a.name,
            'type': a.artifact_type,
            'roi': round(a.roi, 3),
            'uses': a.use_count,
            'smoothed_sr': f"{a.smoothed_success_rate:.0%}",
            'tags': a.tags,
            'content': a.content[:60]
        } for a in active]
        print(json.dumps(output, indent=2, ensure_ascii=False))

    elif args.action == 'sync':
        summary = memory.to_markdown_summary(args.max_tokens)
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
    g_build.set_defaults(func=cmd_genome_build)

    g_ctx = g_subs.add_parser('context', help="Synthesize task-relevant context")
    g_ctx.add_argument('task', help="Task description")
    g_ctx.add_argument('path', nargs='?', default='.', help="Target project root directory")
    g_ctx.add_argument('--max-tokens', type=int, default=1200, help="Maximum synthesized context tokens")
    g_ctx.set_defaults(func=cmd_genome_context)

    # Darwin parser
    p_darwin = subparsers.add_parser('darwin', help="Darwin ROI-based memory evolution commands")
    p_darwin.add_argument('action', choices=['register', 'use', 'evolve', 'list', 'search', 'sync'])
    p_darwin.add_argument('name', nargs='?', help="Artifact name (register)")
    p_darwin.add_argument('type', nargs='?', choices=['pattern', 'lesson', 'skill', 'tool'], help="Artifact type")
    p_darwin.add_argument('content', nargs='?', help="Content / lesson (register)")
    p_darwin.add_argument('--tags', help="Comma-separated tags (e.g. auth,security,db)")
    p_darwin.add_argument('--query', help="Search query string (search)")
    p_darwin.add_argument('--file', help="Read content from file")
    p_darwin.add_argument('--success', choices=['true', 'false'], default='true', help="Usage outcome (use)")
    p_darwin.add_argument('--artifact_id', help="Target artifact ID (use)")
    p_darwin.add_argument('--threshold', type=float, default=0.3, help="ROI prune threshold")
    p_darwin.add_argument('--max-capacity', type=int, default=50, help="Max active artifacts capacity")
    p_darwin.add_argument('--decay', type=float, default=0.95, help="Generational decay multiplier")
    p_darwin.add_argument('--max-tokens', type=int, default=500, help="Markdown summary token budget")
    p_darwin.add_argument('--state', help="State JSON file path")
    p_darwin.add_argument('--agents-file', help="Target AGENTS.md file for sync")
    p_darwin.set_defaults(func=cmd_darwin)

    args = parser.parse_args()
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
