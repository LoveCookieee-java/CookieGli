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
from cookiegli_core.boost_engine import BoostEngine
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

    def __init__(
        self,
        workspace_root: Optional[Path] = None,
        profile: str = "standard",
        server_name: Optional[str] = None
    ):
        self.workspace_root = (workspace_root or Path.cwd()).resolve()
        self.profile = (profile or "standard").lower()
        if self.profile == "full" or server_name:
            self.SERVER_NAME = server_name or "CookieGli_Full"
        else:
            self.SERVER_NAME = server_name or "cookiegli-mcp"
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
        tools = [
            {
                "name": "cookiegli_boost",
                "description": "[01_TASK_BOOST] cookiegli_boost: Primary entrypoint for coding/debugging tasks. Synthesizes Layer 2 dynamic context (<600t) with BM25 symbols + focus skeleton + 2026 reasoning effort.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "The specific task description or query"},
                        "max_tokens": {"type": "integer", "description": "Maximum token budget (default: 600)", "default": 600},
                        "path": {"type": "string", "description": "Repository path (defaults to workspace root)"}
                    },
                    "required": ["task"]
                }
            },
            {
                "name": "cookiegli_search",
                "description": "[02_SYMBOL_IR] cookiegli_search: Industrial Okapi BM25+ full-text search across codebase symbols using SQLite FTS5 BM25+ ranking.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Symbol name or search terms"},
                        "limit": {"type": "integer", "description": "Maximum number of results to return", "default": 20},
                        "path": {"type": "string", "description": "Repository path (defaults to workspace root)"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "cookiegli_find_symbols",
                "description": "[02_SYMBOL_BTREE] cookiegli_find_symbols: Sub-millisecond exact B-Tree symbol lookup for known identifier names (classes, functions, methods).",
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
                "description": "[03_CODE_SKELETON] cookiegli_get_skeleton: Extract folded code skeleton preserving verbatim focus symbol.",
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
                "description": "[04_IMPACT_ANALYSIS] cookiegli_blast_radius: Forward-to-ingress dependency graph & minimal targeted test suite for modified or specified files.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Repository path (defaults to workspace root)"},
                        "file": {"type": "string", "description": "Specific target file to analyze"},
                        "files": {"type": "array", "items": {"type": "string"}, "description": "List of target files to analyze"},
                        "symbol": {"type": "string", "description": "Specific symbol name to analyze"},
                        "max_depth": {"type": "integer", "description": "Maximum BFS traversal depth (default: 3)", "default": 3},
                        "max_tokens": {"type": "integer", "description": "Maximum token budget for compact output (default: 250)", "default": 250},
                        "no_cache": {"type": "boolean", "description": "Disable incremental cache", "default": False}
                    }
                }
            },
            {
                "name": "cookiegli_distill_lesson",
                "description": "[05_ERROR_DISTILLER] cookiegli_distill_lesson: Distill traceback/panics into Darwin rules with Bayesian ROI.",
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
            },
            {
                "name": "cookiegli_get_genome",
                "description": "[06_ARCHITECTURE] cookiegli_get_genome: High-density Layer 1 static codebase architecture map (<600t).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Repository path (defaults to workspace root)"}
                    }
                }
            },
            {
                "name": "cookiegli_synthesize_context",
                "description": "[01_TASK_CONTEXT] cookiegli_synthesize_context: Synthesizes surgical targeted context for a specific coding or debugging task.",
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
                "description": "[07_DARWIN_MEMORY] cookiegli_darwin_record: Knowledge persistence with Bayesian ROI (Laplace-smoothed).",
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
                "description": "[07_DARWIN_MEMORY] cookiegli_darwin_search: Searches learned operational patterns by query, domain scope, and tags.",
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
                "description": "[08_TARGET_SYNC] cookiegli_sync: Sync rules to CLAUDE.md, AGENTS.md, .cursorrules, .windsurfrules.",
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
            }
        ]

        if self.profile == "full":
            tools.insert(0, {
                "name": "cookiegli_full",
                "description": "[00_CENTRAL_DISPATCH] cookiegli_full: Unified polymorphic gateway dispatching to boost, search, find_symbols, skeleton, blast, distill, genome, darwin_record, darwin_search, and sync.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": [
                                "boost",
                                "search",
                                "find_symbols",
                                "skeleton",
                                "blast",
                                "distill",
                                "genome",
                                "darwin_record",
                                "darwin_search",
                                "sync"
                            ],
                            "description": "CookieGli action to execute"
                        },
                        "params": {
                            "type": "object",
                            "description": "Parameters for the chosen action"
                        }
                    },
                    "required": ["action"]
                }
            })

        return tools

    def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> str:
        """Executes an MCP tool call and returns text result."""
        if name == "cookiegli_full":
            action = arguments.get("action")
            if not action:
                raise ValueError("Missing required 'action' parameter for cookiegli_full")
            params = arguments.get("params")
            if isinstance(params, str):
                try:
                    params = json.loads(params)
                except Exception:
                    params = {}
            elif not isinstance(params, dict):
                params = {}
            for k, v in arguments.items():
                if k not in ("action", "params") and k not in params:
                    params[k] = v

            action_map = {
                "boost": "cookiegli_boost",
                "search": "cookiegli_search",
                "find_symbols": "cookiegli_find_symbols",
                "symbol": "cookiegli_find_symbols",
                "symbols": "cookiegli_find_symbols",
                "find": "cookiegli_find_symbols",
                "skeleton": "cookiegli_get_skeleton",
                "get_skeleton": "cookiegli_get_skeleton",
                "blast": "cookiegli_blast_radius",
                "blast_radius": "cookiegli_blast_radius",
                "distill": "cookiegli_distill_lesson",
                "distill_lesson": "cookiegli_distill_lesson",
                "genome": "cookiegli_get_genome",
                "get_genome": "cookiegli_get_genome",
                "darwin_record": "cookiegli_darwin_record",
                "darwin_search": "cookiegli_darwin_search",
                "sync": "cookiegli_sync",
                "context": "cookiegli_synthesize_context",
                "synthesize_context": "cookiegli_synthesize_context",
            }
            if action == "darwin":
                target_tool = "cookiegli_darwin_record" if ("content" in params or "name" in params) else "cookiegli_darwin_search"
            else:
                target_tool = action_map.get(action)

            if not target_tool:
                canonical = [
                    "blast", "boost", "darwin_record", "darwin_search",
                    "distill", "find_symbols", "genome", "search",
                    "skeleton", "sync"
                ]
                raise ValueError(
                    f"Unknown action '{action}' for cookiegli_full. Valid actions: {canonical}"
                )
            return self.handle_tool_call(target_tool, params)

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
            raw_file_path = arguments.get("path") or arguments.get("file_path") or arguments.get("file")
            if not raw_file_path:
                raise ValueError("Missing required 'path' parameter for cookiegli_get_skeleton")
            p = Path(raw_file_path)
            file_path = (self.workspace_root / p).resolve() if not p.is_absolute() else p.resolve()
            if not file_path.is_file():
                raise FileNotFoundError(f"File not found: {file_path}")

            focus_symbol = arguments.get("focus_symbol") or arguments.get("focus")
            max_tokens_val = arguments.get("max_tokens")
            max_tokens = int(max_tokens_val) if max_tokens_val is not None else 600
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

            blast_root = target_path
            if blast_root.is_file():
                if not target_files:
                    target_files = [str(blast_root)]
                blast_root = self.workspace_root

            with BlastRadiusEngine(str(blast_root), use_cache=not no_cache) as engine:
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

        elif name == "cookiegli_boost":
            task = arguments.get("task", "")
            max_tokens_val = arguments.get("max_tokens")
            max_tokens = int(max_tokens_val) if max_tokens_val is not None else 600
            boost_root = self.workspace_root if target_path.is_file() else target_path
            with BoostEngine(str(boost_root)) as boost_engine:
                return boost_engine.synthesize_task_context(task, max_tokens=max_tokens)

        elif name == "cookiegli_search":
            query = arguments.get("query", "")
            limit_val = arguments.get("limit")
            limit = int(limit_val) if limit_val is not None else 20
            search_root = self.workspace_root if target_path.is_file() else target_path
            cache_dir = search_root / '.cookiegli'
            with AstCache(str(cache_dir)) as cache:
                results = cache.search_bm25(query, limit=limit)
                if not results and cache.count() == 0:
                    with AstScanner(str(search_root), use_cache=True, cache_dir=str(cache_dir)) as scanner:
                        scanner.scan()
                    results = cache.search_bm25(query, limit=limit)
            if not results:
                return f"No symbols found matching '{query}'."
            formatted = []
            for r in results:
                score_str = f" [score: {r['score']}]" if 'score' in r else ""
                sig = f" : {r['signature']}" if r.get('signature') else ""
                formatted.append(f"• [{r['entity_type']}] {r['name']} ({r['relative_path']}:{r['line_number']}){sig}{score_str}")
            return "\n".join(formatted)

        else:
            raise ValueError(f"Unknown tool '{name}'")

    def process_rpc_request(self, request: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Processes a single JSON-RPC 2.0 request dict."""
        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params")
        if params is None or not isinstance(params, dict):
            params = {}

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
                        "tools": {},
                        "resources": {}
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
            tool_args = params.get("arguments")
            if tool_args is None or not isinstance(tool_args, dict):
                tool_args = {}
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

        if method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "resources": [
                        {
                            "uri": "mcp://cookiegli/guide",
                            "name": "CookieGli Agent Decision Guide",
                            "mimeType": "text/markdown",
                            "description": "Agent Decision Matrix & Disambiguation Rules for CookieGli tools"
                        }
                    ]
                }
            }

        if method == "resources/read":
            uri = params.get("uri")
            norm_uri = (uri or "").rstrip("/")
            if norm_uri == "mcp://cookiegli/guide":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "contents": [
                            {
                                "uri": "mcp://cookiegli/guide",
                                "mimeType": "text/markdown",
                                "text": self.get_agent_guide_text()
                            }
                        ]
                    }
                }
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32602, "message": f"Resource not found: {uri}"}
            }

        if method == "resources/templates/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "resourceTemplates": []
                }
            }

        # Unsupported method
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }

    @staticmethod
    def get_agent_guide_text() -> str:
        """Returns the Agent Decision Matrix & Tool Disambiguation Guide."""
        return """# CookieGli Agent Decision Guide & Disambiguation Matrix

## Agent Decision Matrix: When to Use Which Tool

| Situation | Recommended Tool | Why Use This Tool? | Tool to AVOID |
| :--- | :--- | :--- | :--- |
| **Starting a new coding/debugging task** | `cookiegli_boost` | Synthesizes Layer 2 dynamic context (<600t): BM25 symbols + skeleton + targeted tests + 2026 reasoning effort. | Do NOT call separate skeleton + symbol search before boosting. |
| **Fuzzy search for symbols by natural keyword** | `cookiegli_search` | SQLite FTS5 Okapi BM25+ full-text search ranked by semantic relevance. | Do NOT use `cookiegli_find_symbols` when keyword is approximate. |
| **Exact match for known function/class name** | `cookiegli_find_symbols` | SQLite B-Tree index lookup with `exact=true`, sub-millisecond (<0.05ms). | Do NOT use BM25 when searching for an exact identifier. |
| **Editing a specific function in a file** | `cookiegli_get_skeleton` | Pass `focus_symbol="target_name"` to fold surrounding code and keep target verbatim. | Do NOT dump the entire raw file. |
| **Before editing or after test failure** | `cookiegli_blast_radius` | Reverse dependency impact graph and minimal targeted test suite. | Do NOT run the entire monolithic test suite. |
| **On test failure, exception, or traceback** | `cookiegli_distill_lesson` | Parses traceback/diff, creates Darwin lesson with Bayesian Laplace ROI. | Do NOT fix bugs without persisting lessons. |
| **Entering unfamiliar codebase or new session** | `cookiegli_get_genome` | Loads Layer 1 static codebase architecture map (<600t). | Do NOT recursively list directories. |
| **Persisting reusable engineering rules** | `cookiegli_darwin_record` | Records rules into persistent Darwin memory with Laplace-smoothed Bayesian ROI. | Do NOT write ad-hoc notes. |
| **Querying learned engineering patterns** | `cookiegli_darwin_search` | Searches learned rules by scope, tags, and text query. | Do NOT repeat past mistakes. |
| **Synchronizing project rules to AI agent configs** | `cookiegli_sync` | Syncs genome and Darwin memory to CLAUDE.md, AGENTS.md, .cursorrules, etc. | Do NOT manually edit agent rule files. |
| **Single unified multi-action gateway** | `cookiegli_full` | Central dispatch hub accepting `action` and `params`. | Ideal for clients with tool slot limits. |

## 2026 Frontier Models Reasoning Calibration
CookieGli is calibrated for July-September 2026 frontier models:
- OpenAI GPT-6 Astra & GPT-5.6 Sol
- Anthropic Claude Fable 5.1 & Claude Opus 5
- Google Gemini 3.8 Flash
- Moonshot Kimi K3
- DeepSeek-V4 Series

Maintain surgical context (<600 tokens) to preserve prefix cache hits and maximize reasoning efficiency.
"""

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
    import argparse
    parser = argparse.ArgumentParser(description="CookieGli Pure-Python MCP Server")
    parser.add_argument("--root", default=".", help="Workspace root directory")
    parser.add_argument("--profile", choices=["standard", "full"], default="full", help="MCP server profile (default: full)")
    parser.add_argument("--name", default=None, help="Custom server name override")
    args, _ = parser.parse_known_args()

    root_path = Path(args.root).resolve()
    server = CookieGliMcpServer(workspace_root=root_path, profile=args.profile, server_name=args.name)
    server.run_stdio()


if __name__ == "__main__":
    main()
