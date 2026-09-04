"""
Tests for CookieGli_Full MCP Architecture:
- Server initialization with profile="full" and custom names
- Tool manifest category prefixes for Agent disambiguation
- Central polymorphic dispatch tool `cookiegli_full`
- MCP Resources (`resources/list`, `resources/read`, `resources/templates/list`)
"""

import sys
import unittest
import tempfile
import shutil
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))

from cookiegli_core.mcp_server import CookieGliMcpServer
from cookiegli_core.ast_scanner import AstScanner


class TestCookieGliMcpFull(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name).resolve()

        # Create sample files for testing tools
        src_dir = self.workspace_root / "src"
        src_dir.mkdir(parents=True, exist_ok=True)

        self.sample_py = src_dir / "user_service.py"
        self.sample_py.write_text(
            'class UserService:\n'
            '    def get_user(self, user_id: int) -> dict:\n'
            '        """Fetch user record by ID."""\n'
            '        return {"id": user_id, "active": True}\n'
            '\n'
            '    def authenticate(self, token: str) -> bool:\n'
            '        return token == "secret"\n',
            encoding="utf-8"
        )

        # Initialize AST scanner cache
        cache_dir = self.workspace_root / ".cookiegli"
        with AstScanner(str(self.workspace_root), use_cache=True, cache_dir=str(cache_dir)) as scanner:
            scanner.scan()

        self.server = CookieGliMcpServer(workspace_root=self.workspace_root, profile="full")

    def tearDown(self):
        if hasattr(self, 'server') and self.server:
            self.server.close()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_initialize_full_profile(self):
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        }
        resp = self.server.process_rpc_request(req)
        self.assertEqual(resp["id"], 1)
        self.assertEqual(resp["result"]["serverInfo"]["name"], "CookieGli_Full")
        self.assertIn("tools", resp["result"]["capabilities"])
        self.assertIn("resources", resp["result"]["capabilities"])

    def test_custom_server_name(self):
        with CookieGliMcpServer(workspace_root=self.workspace_root, profile="full", server_name="CustomServer") as custom_srv:
            req = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "initialize",
                "params": {}
            }
            resp = custom_srv.process_rpc_request(req)
            self.assertEqual(resp["result"]["serverInfo"]["name"], "CustomServer")

    def test_tools_list_category_prefixes(self):
        req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/list",
            "params": {}
        }
        resp = self.server.process_rpc_request(req)
        tools = resp["result"]["tools"]
        tool_dict = {t["name"]: t for t in tools}

        # Check that central dispatch tool is present
        self.assertIn("cookiegli_full", tool_dict)
        self.assertTrue(tool_dict["cookiegli_full"]["description"].startswith("[00_CENTRAL_DISPATCH]"))

        # Check category prefixes
        expected_prefixes = {
            "cookiegli_boost": "[01_TASK_BOOST]",
            "cookiegli_synthesize_context": "[01_TASK_CONTEXT]",
            "cookiegli_search": "[02_SYMBOL_IR]",
            "cookiegli_find_symbols": "[02_SYMBOL_BTREE]",
            "cookiegli_get_skeleton": "[03_CODE_SKELETON]",
            "cookiegli_blast_radius": "[04_IMPACT_ANALYSIS]",
            "cookiegli_distill_lesson": "[05_ERROR_DISTILLER]",
            "cookiegli_get_genome": "[06_ARCHITECTURE]",
            "cookiegli_darwin_record": "[07_DARWIN_MEMORY]",
            "cookiegli_darwin_search": "[07_DARWIN_MEMORY]",
            "cookiegli_sync": "[08_TARGET_SYNC]",
        }

        for tool_name, prefix in expected_prefixes.items():
            self.assertIn(tool_name, tool_dict, f"Missing tool {tool_name}")
            self.assertTrue(
                tool_dict[tool_name]["description"].startswith(prefix),
                f"Tool {tool_name} description does not start with {prefix}: {tool_dict[tool_name]['description']}"
            )

    def test_cookiegli_full_action_genome(self):
        req = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_full",
                "arguments": {
                    "action": "genome",
                    "params": {"path": str(self.workspace_root)}
                }
            }
        }
        resp = self.server.process_rpc_request(req)
        self.assertNotIn("isError", resp["result"])
        content = resp["result"]["content"][0]["text"]
        self.assertIn("UserService", content)

    def test_cookiegli_full_action_boost(self):
        req = {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_full",
                "arguments": {
                    "action": "boost",
                    "params": {
                        "task": "authenticate user token",
                        "path": str(self.workspace_root)
                    }
                }
            }
        }
        resp = self.server.process_rpc_request(req)
        self.assertNotIn("isError", resp["result"])
        content = resp["result"]["content"][0]["text"]
        self.assertIn("LAYER 2", content)

    def test_cookiegli_full_action_find_symbols_and_search(self):
        # find_symbols
        req_sym = {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_full",
                "arguments": {
                    "action": "find_symbols",
                    "params": {
                        "query": "UserService",
                        "path": str(self.workspace_root)
                    }
                }
            }
        }
        resp_sym = self.server.process_rpc_request(req_sym)
        self.assertNotIn("isError", resp_sym["result"])
        self.assertIn("UserService", resp_sym["result"]["content"][0]["text"])

        # search (BM25)
        req_search = {
            "jsonrpc": "2.0",
            "id": 13,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_full",
                "arguments": {
                    "action": "search",
                    "params": {
                        "query": "authenticate",
                        "path": str(self.workspace_root)
                    }
                }
            }
        }
        resp_search = self.server.process_rpc_request(req_search)
        self.assertNotIn("isError", resp_search["result"])
        self.assertIn("authenticate", resp_search["result"]["content"][0]["text"])

    def test_cookiegli_full_action_skeleton(self):
        req = {
            "jsonrpc": "2.0",
            "id": 14,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_full",
                "arguments": {
                    "action": "skeleton",
                    "params": {
                        "path": str(self.sample_py),
                        "focus_symbol": "authenticate"
                    }
                }
            }
        }
        resp = self.server.process_rpc_request(req)
        self.assertNotIn("isError", resp["result"])
        content = resp["result"]["content"][0]["text"]
        self.assertIn("def authenticate", content)
        self.assertIn("token == \"secret\"", content)

    def test_cookiegli_full_action_blast(self):
        req = {
            "jsonrpc": "2.0",
            "id": 15,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_full",
                "arguments": {
                    "action": "blast",
                    "params": {
                        "file": str(self.sample_py),
                        "path": str(self.workspace_root)
                    }
                }
            }
        }
        resp = self.server.process_rpc_request(req)
        self.assertNotIn("isError", resp["result"])
        content = resp["result"]["content"][0]["text"]
        self.assertIn("BLAST_RADIUS", content)

    def test_cookiegli_full_action_distill(self):
        tb = (
            'Traceback (most recent call last):\n'
            '  File "src/user_service.py", line 5, in get_user\n'
            'KeyError: "user_not_found"\n'
        )
        req = {
            "jsonrpc": "2.0",
            "id": 16,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_full",
                "arguments": {
                    "action": "distill",
                    "params": {
                        "traceback": tb,
                        "fix": "Safely return empty dictionary on missing user",
                        "scope": "core.user"
                    }
                }
            }
        }
        resp = self.server.process_rpc_request(req)
        self.assertNotIn("isError", resp["result"])
        content = resp["result"]["content"][0]["text"]
        parsed = json.loads(content)
        self.assertEqual(parsed["error"]["type"], "KeyError")
        self.assertEqual(parsed["lesson"]["scope"], "core.user")

    def test_cookiegli_full_action_darwin_record_and_search(self):
        req_rec = {
            "jsonrpc": "2.0",
            "id": 17,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_full",
                "arguments": {
                    "action": "darwin_record",
                    "params": {
                        "name": "cache_invalidation",
                        "content": "Invalidate cache immediately upon mutation",
                        "scope": "core.cache",
                        "tags": ["cache", "mutation"]
                    }
                }
            }
        }
        resp_rec = self.server.process_rpc_request(req_rec)
        self.assertNotIn("isError", resp_rec["result"])
        self.assertIn("Registered and recorded", resp_rec["result"]["content"][0]["text"])

        req_search = {
            "jsonrpc": "2.0",
            "id": 18,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_full",
                "arguments": {
                    "action": "darwin_search",
                    "params": {
                        "query": "invalidate",
                        "scope": "core.cache"
                    }
                }
            }
        }
        resp_search = self.server.process_rpc_request(req_search)
        self.assertNotIn("isError", resp_search["result"])
        self.assertIn("Invalidate cache immediately", resp_search["result"]["content"][0]["text"])

    def test_cookiegli_full_action_sync(self):
        req = {
            "jsonrpc": "2.0",
            "id": 19,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_full",
                "arguments": {
                    "action": "sync",
                    "params": {
                        "target": "claude",
                        "path": str(self.workspace_root)
                    }
                }
            }
        }
        resp = self.server.process_rpc_request(req)
        self.assertNotIn("isError", resp["result"])
        self.assertTrue((self.workspace_root / "CLAUDE.md").exists())

    def test_cookiegli_full_flat_parameters(self):
        # Flat arguments without nested "params" dict should also work
        req = {
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_full",
                "arguments": {
                    "action": "find_symbols",
                    "query": "UserService",
                    "path": str(self.workspace_root)
                }
            }
        }
        resp = self.server.process_rpc_request(req)
        self.assertNotIn("isError", resp["result"])
        self.assertIn("UserService", resp["result"]["content"][0]["text"])

    def test_cookiegli_full_unknown_action(self):
        req = {
            "jsonrpc": "2.0",
            "id": 21,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_full",
                "arguments": {
                    "action": "unknown_action_xyz",
                    "params": {}
                }
            }
        }
        resp = self.server.process_rpc_request(req)
        self.assertTrue(resp["result"]["isError"])
        self.assertIn("Unknown action 'unknown_action_xyz'", resp["result"]["content"][0]["text"])

    def test_resources_list(self):
        req = {
            "jsonrpc": "2.0",
            "id": 30,
            "method": "resources/list",
            "params": {}
        }
        resp = self.server.process_rpc_request(req)
        self.assertEqual(resp["id"], 30)
        resources = resp["result"]["resources"]
        self.assertEqual(len(resources), 1)
        r = resources[0]
        self.assertEqual(r["uri"], "mcp://cookiegli/guide")
        self.assertEqual(r["name"], "CookieGli Agent Decision Guide")
        self.assertEqual(r["mimeType"], "text/markdown")

    def test_resources_read_success(self):
        req = {
            "jsonrpc": "2.0",
            "id": 31,
            "method": "resources/read",
            "params": {"uri": "mcp://cookiegli/guide"}
        }
        resp = self.server.process_rpc_request(req)
        self.assertEqual(resp["id"], 31)
        contents = resp["result"]["contents"]
        self.assertEqual(len(contents), 1)
        c = contents[0]
        self.assertEqual(c["uri"], "mcp://cookiegli/guide")
        self.assertEqual(c["mimeType"], "text/markdown")
        self.assertIn("CookieGli Agent Decision Guide", c["text"])
        self.assertIn("cookiegli_boost", c["text"])
        self.assertIn("cookiegli_search", c["text"])
        self.assertIn("cookiegli_blast_radius", c["text"])
        self.assertIn("2026 Frontier Models Reasoning Calibration", c["text"])

    def test_resources_read_not_found(self):
        req = {
            "jsonrpc": "2.0",
            "id": 32,
            "method": "resources/read",
            "params": {"uri": "mcp://cookiegli/nonexistent"}
        }
        resp = self.server.process_rpc_request(req)
        self.assertEqual(resp["id"], 32)
        self.assertEqual(resp["error"]["code"], -32602)
        self.assertIn("Resource not found", resp["error"]["message"])

    def test_resources_templates_list(self):
        req = {
            "jsonrpc": "2.0",
            "id": 33,
            "method": "resources/templates/list",
            "params": {}
        }
        resp = self.server.process_rpc_request(req)
        self.assertEqual(resp["id"], 33)
        self.assertEqual(resp["result"]["resourceTemplates"], [])

    def test_cookiegli_full_action_darwin_alias_and_auto_routing(self):
        # 1. action="darwin" with content -> auto-routes to darwin_record
        rec_req = {
            "jsonrpc": "2.0",
            "id": 40,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_full",
                "arguments": {
                    "action": "darwin",
                    "params": {
                        "name": "atomic_persist",
                        "content": "Always use atomic file write with temp replace",
                        "scope": "storage"
                    }
                }
            }
        }
        rec_resp = self.server.process_rpc_request(rec_req)
        self.assertNotIn("isError", rec_resp["result"])
        self.assertIn("Registered and recorded", rec_resp["result"]["content"][0]["text"])

        # 2. action="darwin" with query -> auto-routes to darwin_search
        search_req = {
            "jsonrpc": "2.0",
            "id": 41,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_full",
                "arguments": {
                    "action": "darwin",
                    "params": {
                        "query": "atomic",
                        "scope": "storage"
                    }
                }
            }
        }
        search_resp = self.server.process_rpc_request(search_req)
        self.assertNotIn("isError", search_resp["result"])
        self.assertIn("atomic file write", search_resp["result"]["content"][0]["text"])

    def test_cookiegli_full_action_aliases(self):
        # action="symbol" alias for find_symbols
        req_sym = {
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_full",
                "arguments": {
                    "action": "symbol",
                    "params": {"query": "UserService"}
                }
            }
        }
        resp_sym = self.server.process_rpc_request(req_sym)
        self.assertNotIn("isError", resp_sym["result"])
        self.assertIn("UserService", resp_sym["result"]["content"][0]["text"])

        # action="blast_radius" alias for blast
        req_blast = {
            "jsonrpc": "2.0",
            "id": 43,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_full",
                "arguments": {
                    "action": "blast_radius",
                    "params": {"file": str(self.sample_py)}
                }
            }
        }
        resp_blast = self.server.process_rpc_request(req_blast)
        self.assertNotIn("isError", resp_blast["result"])
        self.assertIn("BLAST_RADIUS", resp_blast["result"]["content"][0]["text"])

        # action="context" alias for synthesize_context
        req_ctx = {
            "jsonrpc": "2.0",
            "id": 44,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_full",
                "arguments": {
                    "action": "context",
                    "params": {"task": "authenticate user"}
                }
            }
        }
        resp_ctx = self.server.process_rpc_request(req_ctx)
        self.assertNotIn("isError", resp_ctx["result"])
        self.assertIn("TASK CONTEXT", resp_ctx["result"]["content"][0]["text"])

    def test_cookiegli_full_params_as_json_string(self):
        req = {
            "jsonrpc": "2.0",
            "id": 45,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_full",
                "arguments": {
                    "action": "find_symbols",
                    "params": json.dumps({"query": "UserService"})
                }
            }
        }
        resp = self.server.process_rpc_request(req)
        self.assertNotIn("isError", resp["result"])
        self.assertIn("UserService", resp["result"]["content"][0]["text"])

    def test_process_rpc_null_params_handling(self):
        # Null params in resources/read should return clean error without crashing server
        req = {
            "jsonrpc": "2.0",
            "id": 46,
            "method": "resources/read",
            "params": None
        }
        resp = self.server.process_rpc_request(req)
        self.assertEqual(resp["id"], 46)
        self.assertEqual(resp["error"]["code"], -32602)

        # Null arguments in tools/call should execute safely
        req_tool = {
            "jsonrpc": "2.0",
            "id": 47,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_boost",
                "arguments": None
            }
        }
        resp_tool = self.server.process_rpc_request(req_tool)
        self.assertEqual(resp_tool["id"], 47)
        self.assertNotIn("isError", resp_tool["result"])

    def test_resources_read_trailing_slash(self):
        req = {
            "jsonrpc": "2.0",
            "id": 48,
            "method": "resources/read",
            "params": {"uri": "mcp://cookiegli/guide/"}
        }
        resp = self.server.process_rpc_request(req)
        self.assertEqual(resp["id"], 48)
        self.assertIn("contents", resp["result"])
        self.assertIn("CookieGli Agent Decision Guide", resp["result"]["contents"][0]["text"])

    def test_skeleton_file_path_and_focus_aliases(self):
        # file_path instead of path, focus instead of focus_symbol
        req = {
            "jsonrpc": "2.0",
            "id": 49,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_get_skeleton",
                "arguments": {
                    "file_path": str(self.sample_py),
                    "focus": "authenticate"
                }
            }
        }
        resp = self.server.process_rpc_request(req)
        self.assertNotIn("isError", resp["result"])
        content = resp["result"]["content"][0]["text"]
        self.assertIn("def authenticate", content)

    def test_blast_radius_single_file_path(self):
        # passing a file as path should work without treating the file as a directory
        req = {
            "jsonrpc": "2.0",
            "id": 50,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_blast_radius",
                "arguments": {
                    "path": str(self.sample_py)
                }
            }
        }
        resp = self.server.process_rpc_request(req)
        self.assertNotIn("isError", resp["result"])
        content = resp["result"]["content"][0]["text"]
        self.assertIn("BLAST_RADIUS", content)

    def test_search_and_boost_none_token_limits(self):
        # None max_tokens in boost
        req_boost = {
            "jsonrpc": "2.0",
            "id": 51,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_boost",
                "arguments": {
                    "task": "testing None token budget",
                    "max_tokens": None
                }
            }
        }
        resp_boost = self.server.process_rpc_request(req_boost)
        self.assertNotIn("isError", resp_boost["result"])

        # None limit in search
        req_search = {
            "jsonrpc": "2.0",
            "id": 52,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_search",
                "arguments": {
                    "query": "UserService",
                    "limit": None
                }
            }
        }
        resp_search = self.server.process_rpc_request(req_search)
        self.assertNotIn("isError", resp_search["result"])
        self.assertIn("UserService", resp_search["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
