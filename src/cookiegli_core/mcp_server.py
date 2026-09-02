"""
Pure Python stdlib MCP Server for CookieGli / Glimax.
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


class CookieGliMcpServer:
    """Standard Model Context Protocol (MCP) server over STDIO."""

    PROTOCOL_VERSION = "2024-11-05"
    SERVER_NAME = "cookiegli-mcp"
    SERVER_VERSION = "2.2.0"

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = (workspace_root or Path.cwd()).resolve()
        self.genome_engine = GenomeEngine(str(self.workspace_root))
        self.darwin_memory = DarwinMemory(state_file=str(self.workspace_root / ".cookiegli" / "darwin_state.json"))

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
            }
        ]

    def handle_tool_call(self, name: str, arguments: Dict[str, Any]) -> str:
        """Executes an MCP tool call and returns text result."""
        target_path = Path(arguments.get("path") or self.workspace_root).resolve()

        if name == "cookiegli_get_genome":
            engine = self.genome_engine if target_path == self.workspace_root else GenomeEngine(str(target_path))
            genome = engine.build()
            return genome.to_compact()

        elif name == "cookiegli_synthesize_context":
            task = arguments.get("task", "")
            engine = self.genome_engine if target_path == self.workspace_root else GenomeEngine(str(target_path))
            genome = engine.build()
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
            darwin_text = self.darwin_memory.to_markdown_summary()
            synced = TargetManager.sync(target, target_path, genome_text=genome_text, darwin_text=darwin_text)
            return f"Successfully synchronized target(s): {json.dumps(synced)}"

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
