"""Exercise JSON-RPC initialization, discovery, and tools through actual stdio."""

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import threading

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


def test_real_stdio_client_to_http():
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append((self.path, self.headers.get("Authorization")))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "execution": "local_sample_only"}).encode())

        def log_message(self, *args):
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()

    async def exercise():
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "semantic_hub_mcp.server"],
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src"),
                 "SEMANTIC_HUB_URL": f"http://127.0.0.1:{http.server_port}", "SEMANTIC_HUB_API_TOKEN": "test-secret"},
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert len(tools.tools) == 12
                result = await session.call_tool("hub_status", {})
                assert not result.is_error
                assert result.structured_content["execution"] == "local_sample_only"

    try:
        asyncio.run(exercise())
        assert seen == [("/api/semantic-hub/v1/capabilities", "Bearer test-secret")]
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=5)
