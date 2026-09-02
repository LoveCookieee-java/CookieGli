import sys
import unittest
import tempfile
import shutil
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))

from cookiegli_core.mcp_server import CookieGliMcpServer


class TestCookieGliMcpServer(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        # create dummy python file
        py_file = self.test_dir / "sample.py"
        py_file.write_text("class Calculator:\n    def add(self, a: int, b: int) -> int:\n        return a + b\n", encoding="utf-8")
        self.server = CookieGliMcpServer(workspace_root=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_initialize(self):
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {}
        }
        resp = self.server.process_rpc_request(req)
        self.assertEqual(resp["id"], 1)
        self.assertEqual(resp["result"]["serverInfo"]["name"], "cookiegli-mcp")
        self.assertIn("tools", resp["result"]["capabilities"])

    def test_tools_list(self):
        req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        resp = self.server.process_rpc_request(req)
        tools = resp["result"]["tools"]
        tool_names = [t["name"] for t in tools]
        self.assertIn("cookiegli_get_genome", tool_names)
        self.assertIn("cookiegli_synthesize_context", tool_names)
        self.assertIn("cookiegli_darwin_record", tool_names)
        self.assertIn("cookiegli_darwin_search", tool_names)
        self.assertIn("cookiegli_sync", tool_names)

    def test_tool_call_get_genome(self):
        req = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_get_genome",
                "arguments": {"path": str(self.test_dir)}
            }
        }
        resp = self.server.process_rpc_request(req)
        self.assertEqual(resp["id"], 3)
        content = resp["result"]["content"][0]["text"]
        self.assertIn("Calculator", content)

    def test_tool_call_darwin_record_and_search(self):
        record_req = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_darwin_record",
                "arguments": {
                    "name": "math_guard",
                    "artifact_type": "pattern",
                    "content": "Always validate inputs to avoid division by zero",
                    "success": True,
                    "scope": "core.math",
                    "tags": ["math", "validation"]
                }
            }
        }
        resp = self.server.process_rpc_request(record_req)
        self.assertIn("Registered and recorded", resp["result"]["content"][0]["text"])

        search_req = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_darwin_search",
                "arguments": {
                    "query": "division",
                    "scope": "core"
                }
            }
        }
        search_resp = self.server.process_rpc_request(search_req)
        self.assertIn("Always validate inputs", search_resp["result"]["content"][0]["text"])

    def test_tool_call_sync(self):
        req = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "cookiegli_sync",
                "arguments": {
                    "target": "claude",
                    "path": str(self.test_dir)
                }
            }
        }
        resp = self.server.process_rpc_request(req)
        self.assertIn("Successfully synchronized", resp["result"]["content"][0]["text"])
        self.assertTrue((self.test_dir / "CLAUDE.md").exists())

    def test_unknown_method(self):
        req = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "non_existent_method"
        }
        resp = self.server.process_rpc_request(req)
        self.assertEqual(resp["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
