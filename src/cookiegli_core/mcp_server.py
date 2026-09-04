"""
Pure Python stdlib MCP Server for CookieGli.
Conforms to Model Context Protocol (MCP) JSON-RPC 2.0 over STDIO.
Zero third-party dependencies.
"""

import sys
import json
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from cookiegli_core.genome_engine import GenomeEngine
from cookiegli_core.darwin_memory import DarwinMemory
from cookiegli_core.adapters import TargetManager
from cookiegli_core.cache_db import AstCache
from cookiegli_core.ast_scanner import AstScanner
from cookiegli_core.skeletonizer import CodeSkeletonizer
from cookiegli_core.blast_radius import BlastRadiusEngine, BlastRadiusReport
from cookiegli_core.distiller import (
    ErrorDistiller,
    clean_darwin_summary,
    resolve_darwin_state_path,
)


class CookieGliMcpServer:
    """Standard Model Context Protocol (MCP) server over STDIO."""

    PROTOCOL_VERSION = "2024-11-05"
    SERVER_NAME = "cookiegli-mcp"
    SERVER_VERSION = "2.2.0"

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = (workspace_root or Path.cwd()).resolve()
        self.genome_engine = GenomeEngine(str(self.workspace_root))
        self.state_file = resolve_darwin_state_path(self.workspace_root)
        self.darwin_memory = DarwinMemory(state_file=str(self.state_file))

    def close(self) -> None:
        """Release underlying genome engine and cache resources cleanly."""
        if hasattr(self, 'genome_engine') and self.genome_engine:
            try:
                self.genome_engine.close()
            except Exception:
                pass
            self.genome_engine = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def get_tools_manifest(self) -> List[Dict[str, Any]]:
        """Returns the list of available MCP tools and schemas."""
        return [
            {
                "name": "cookiegli_get_genome",
                "description": "Extracts high-density (<600 tokens) AST codebase architecture genome.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Repository path (defaults to workspace root)"}
                    }
                }
            },
            {
                "name": "cookiegli_synthesize_context",
                "description": "Synthesizes surgical targeted context for a specific coding or debugging task.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "The specific task description or query"},
                        "path": {"type": "string", "description": "Repository path (defaults to workspace root)"}
                    },
                    "required": ["task"]
                }
            },
            {
                "name": "cookiegli_darwin_record",
                "description": "Records an engineering failure-to-success pattern with Laplace-smoothed Bayesian ROI.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Short identifier for the artifact"},
                        "artifact_type": {"type": "string", "enum": ["pattern", "lesson", "tool"], "default": "pattern"},
                        "content": {"type": "string", "description": "Concrete actionable learning rule"},
                        "success": {"type": "boolean", "description": "Whether the outcome was successful", "default": True},
                        "scope": {"type": "string", "description": "Domain namespace e.g. backend.auth, frontend.ui"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Keywords for indexing"}
                    },
                    "required": ["name", "content"]
                }
            },
            {
                "name": "cookiegli_darwin_search",
                "description": "Searches learned operational patterns by query, domain scope, and tags.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Text query to search for"},
                        "scope": {"type": "string", "description": "Domain scope filter"},
                        "tags": {"type": "array", "items": {"type": "string"}, "description": "Tag filters"}
                    }
                }
            },
            {
                "name": "cookiegli_sync",
                "description": "Synchronizes AST genome and Darwin memories to AI agent configs (claude, codex, antigravity, cursor, windsurf, all).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "enum": ["claude", "codex", "antigravity", "cursor", "windsurf", "all"],
                            "default": "all"
                        },
                        "path": {"type": "string", "description": "Repository root path"}
                    }
                }
            },
            {
                "name": "cookiegli_find_symbols",
                "description": "Fast indexed B-Tree symbol search across the codebase (classes, functions, methods) with sub-millisecond retrieval.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Symbol name or substring to search"},
                        "entity_type": {
                            "type": "string",
                            "enum": ["class", "function", "method", "interface", "struct", "arrow_function"],
                            "description": "Filter by entity type"
                        },
                        "exact": {"type": "boolean", "description": "Exact match vs substring match", "default": False},
                        "limit": {"type": "integer", "description": "Maximum number of results to return", "default": 50},
                        "path": {"type": "string", "description": "Filter by file path or repository root"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "cookiegli_get_skeleton",
                "description": "Extracts compact code skeleton with folded function bodies and optional verbatim focus symbol.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Source file path to skeletonize"},
                        "focus_symbol": {"type": "string", "description": "Function or method name to preserve verbatim"},
                        "max_tokens": {"type": "integer", "description": "Maximum token budget (default: 600)", "default": 600},
                        "no_cache": {"type": "boolean", "description": "Disable cache", "default": False}
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "cookiegli_blast_radius",
                "description": "Analyzes Git blast radius and downstream dependency impact graph for modified or specified files.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Repository path (defaults to workspace root)"},
                        "file": {"type": "string", "description": "Specific target file to analyze"},
                        "symbol": {"type": "string", "description": "Specific symbol name to analyze"},
                        "max_depth": {"type": "integer", "description": "Maximum BFS traversal depth (default: 3)", "default": 3},
                        "max_tokens": {"type": "integer", "description": "Maximum token budget for compact output (default: 250)", "default": 250},
                        "no_cache": {"type": "boolean", "description": "Disable incremental cache", "default": False}
                    }
                }
            },
            {
                "name": "cookiegli_distill_lesson",
                "description": "Distills test failures, runtime panics, or stack traces into actionable Darwin learned patterns with Bayesian ROI.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "traceback": {"type": "string", "description": "Error traceback, panic, or test failure log text"},
                        "diff": {"type": "string", "description": "Optional git diff or code patch representing the fix"},
                        "fix": {"type": "string", "description": "Optional human description of what was fixed"},
                        "scope": {"type": "string", "description": "Optional domain namespace override (e.g. core.cache, backend.auth)"},
                        "auto_register": {"type": "boolean", "description": "Whether to auto-register in Darwin memory pool", "default": True},
                        "sync_targets": {"type": "string", "enum": ["claude", "codex", "antigravity", "cursor", "windsurf", "all"], "description": "Optional target to sync memory to"}
                    },
                    "required": ["traceback"]
                }
            }
        ]

    def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> str:
        """Executes an MCP tool call and returns text result."""
        raw_path = arguments.get("path")
        if raw_path:
            p = Path(raw_path)
            target_path = (self.workspace_root / p).resolve() if not p.is_absolute() else p.resolve()
        else:
            target_path = self.workspace_root

        if name == "cookiegli_get_genome":
            engine = self.genome_engine if target_path == self.workspace_root else GenomeEngine(str(target_path))
            genome = engine.build()
            if target_path != self.workspace_root:
                engine.close()
            return genome.to_compact()

        elif name == "cookiegli_synthesize_context":
            task = arguments.get("task", "")
            engine = self.genome_engine if target_path == self.workspace_root else GenomeEngine(str(target_path))
            genome = engine.build()
            if target_path != self.workspace_root:
                engine.close()
            return genome.synthesize_task_context(task)

        elif name == "cookiegli_darwin_record":
            art_name = arguments.get("name", "learning")
            art_type = arguments.get("artifact_type", "pattern")
            content = arguments.get("content", "")
            success = arguments.get("success", True)
            scope = arguments.get("scope", "general")
            tags = arguments.get("tags", [])
            
            art = self.darwin_memory.register(
                name=art_name,
                artifact_type=art_type,
                content=content,
                scope=scope,
                tags=tags
            )
            self.darwin_memory.record_usage(art.id, success=success)
            return f"Registered and recorded artifact {art.id} '{art_name}' (smoothed ROI: {art.smoothed_success_rate:.2f})."

        elif name == "cookiegli_darwin_search":
            query = arguments.get("query", "")
            scope = arguments.get("scope")
            tags = arguments.get("tags")
            results = self.darwin_memory.search(query=query, scope=scope, tags=tags)
            if not results:
                return "No matching patterns found."
            lines = [r.to_summary_line() for r in results]
            return "\n".join(lines)

        elif name == "cookiegli_sync":
            target = arguments.get("target", "all")
            engine = self.genome_engine if target_path == self.workspace_root else GenomeEngine(str(target_path))
            genome = engine.build()
            genome_text = genome.to_compact()
            darwin_text = clean_darwin_summary(self.darwin_memory.to_markdown_summary())
            synced = TargetManager.sync(target, target_path, genome_text=genome_text, darwin_text=darwin_text)
            if target_path != self.workspace_root:
                engine.close()
            return f"Successfully synchronized target(s): {json.dumps(synced)}"

        elif name == "cookiegli_find_symbols":
            query = arguments.get("query", "")
            entity_type = arguments.get("entity_type")
            exact = arguments.get("exact", False)
            limit = arguments.get("limit", 50)

            # Determine appropriate workspace/cache root vs filter path
            if target_path.is_file() or (not (target_path / ".cookiegli").exists() and (self.workspace_root / ".cookiegli").exists()):
                cache_root = self.workspace_root
                filter_path = raw_path
            elif (target_path / ".cookiegli").exists():
                cache_root = target_path
                filter_path = None
            else:
                cache_root = target_path if target_path.is_dir() else self.workspace_root
                filter_path = raw_path if target_path.is_file() else None

            cache_dir = cache_root / ".cookiegli"
            with AstCache(str(cache_dir)) as cache:
                results = cache.find_symbols(
                    query=query,
                    entity_type=entity_type,
                    exact=exact,
                    limit=limit,
                    path=filter_path
                )
                if not results and cache.count() == 0:
                    with AstScanner(str(cache_root), use_cache=True, cache_dir=str(cache_dir)) as scanner:
                        scanner.scan()
                    results = cache.find_symbols(
                        query=query,
                        entity_type=entity_type,
                        exact=exact,
                        limit=limit,
                        path=filter_path
                    )

            if not results:
                return f"No symbols found matching '{query}'."

            formatted = []
            for r in results:
                sig = f" : {r['signature']}" if r.get('signature') else ""
                formatted.append(f"• [{r['entity_type']}] {r['name']} ({r['relative_path']}:{r['line_number']}){sig}")
            return "\n".join(formatted)

        elif name == "cookiegli_get_skeleton":
            raw_file_path = arguments.get("path")
            if not raw_file_path:
                raise ValueError("Missing required 'path' parameter for cookiegli_get_skeleton")
            p = Path(raw_file_path)
            file_path = (self.workspace_root / p).resolve() if not p.is_absolute() else p.resolve()
            if not file_path.is_file():
                raise FileNotFoundError(f"File not found: {file_path}")

            focus_symbol = arguments.get("focus_symbol")
            max_tokens = arguments.get("max_tokens", 600)
            no_cache = arguments.get("no_cache", False)

            with CodeSkeletonizer(str(self.workspace_root), use_cache=not no_cache) as skel:
                result = skel.skeletonize_file(
                    file_path,
                    focus_symbol=focus_symbol,
                    max_tokens=max_tokens,
                )
            return result.skeleton

        elif name == "cookiegli_blast_radius":
            target_file = arguments.get("file")
            target_files_arg = arguments.get("files")
            symbol = arguments.get("symbol")
            max_depth = arguments.get("max_depth", 3)
            max_tokens = arguments.get("max_tokens", 250)
            no_cache = arguments.get("no_cache", False)

            if target_files_arg and isinstance(target_files_arg, list):
                target_files = target_files_arg
            elif target_file:
                target_files = [target_file]
            else:
                target_files = None

            with BlastRadiusEngine(str(target_path), use_cache=not no_cache) as engine:
                report = engine.analyze(
                    target_files=target_files,
                    symbol=symbol,
                    max_depth=max_depth
                )
                return report.to_compact(max_tokens=max_tokens)

        elif name == "cookiegli_distill_lesson":
            traceback_text = arguments.get("traceback", "")
            if not traceback_text:
                raise ValueError("Missing required 'traceback' parameter for cookiegli_distill_lesson")
            diff_text = arguments.get("diff")
            fix_desc = arguments.get("fix")
            scope_override = arguments.get("scope")
            auto_register = arguments.get("auto_register", True)
            sync_targets = arguments.get("sync_targets")

            distiller = ErrorDistiller(workspace_root=self.workspace_root, memory=self.darwin_memory)
            error, lesson, artifact = distiller.distill(
                log_text=traceback_text,
                diff_text=diff_text,
                fix_description=fix_desc,
                auto_register=auto_register,
                sync_targets=sync_targets,
                scope=scope_override
            )

            res = {
                "error": {
                    "type": error.error_type,
                    "message": error.error_message,
                    "runner": error.runner,
                    "root_cause": f"{error.root_cause_frame.file}:{error.root_cause_frame.line}" if error.root_cause_frame else None
                },
                "lesson": {
                    "name": lesson.name,
                    "scope": lesson.scope,
                    "content": lesson.content,
                    "roi": round(lesson.roi, 3)
                },
                "registered": artifact.id if artifact else None
            }
            return json.dumps(res, indent=2)

        else:
            raise ValueError(f"Unknown tool '{name}'")

    def process_rpc_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Processes a single JSON-RPC 2.0 request dict."""
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params", {})

        if not method:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32600, "message": "Invalid Request: missing method"}
            }

        # Handle MCP Lifecycle
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": self.PROTOCOL_VERSION,
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": self.SERVER_NAME,
                        "version": self.SERVER_VERSION
                    }
                }
            }

        if method in ("notifications/initialized", "initialized"):
            return None  # Notifications do not receive a response

        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}

        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": self.get_tools_manifest()
                }
            }

        if method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            try:
                res_text = self.handle_tool_call(tool_name, tool_args)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": res_text}
                        ]
                    }
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": f"Error executing tool {tool_name}: {str(e)}"}
                        ],
                        "isError": True
                    }
                }

        # Unsupported method
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }

    def run_stdio(self) -> None:
        """Runs the MCP server reading from sys.stdin and writing to sys.stdout."""
        while True:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue

                req = json.loads(line)
                resp = self.process_rpc_request(req)
                if resp is not None:
                    sys.stdout.write(json.dumps(resp) + "\n")
                    sys.stdout.flush()
            except Exception as e:
                err_resp = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error or fatal exception: {str(e)}"}
                }
                sys.stdout.write(json.dumps(err_resp) + "\n")
                sys.stdout.flush()


def main():
    server = CookieGliMcpServer()
    server.run_stdio()


if __name__ == "__main__":
    main()
