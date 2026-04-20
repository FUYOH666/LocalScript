from __future__ import annotations

import json
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from localscript.demo_proxy import build_proxy_server


class _UpstreamHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/v1/models":
            payload = {
                "object": "list",
                "data": [{"id": "qwen2.5-coder:7b"}],
            }
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/v1/chat/completions":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else b""
            request_json = json.loads(body.decode("utf-8"))
            payload = {
                "choices": [
                    {
                        "message": {
                            "content": f"model={request_json['model']}",
                        }
                    }
                ]
            }
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
            return
        self.send_error(404)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


def _serve_in_thread(server) -> threading.Thread:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


def test_demo_proxy_forwards_models_and_chat() -> None:
    upstream = ThreadingHTTPServer(("127.0.0.1", 0), _UpstreamHandler)
    _serve_in_thread(upstream)
    upstream_port = upstream.server_address[1]

    proxy = build_proxy_server(
        listen_host="127.0.0.1",
        listen_port=0,
        upstream_base_url=f"http://127.0.0.1:{upstream_port}",
        timeout_s=5.0,
    )
    _serve_in_thread(proxy)
    proxy_port = proxy.server_address[1]

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{proxy_port}/v1/models", timeout=5) as response:
            models = json.load(response)
        assert models["data"][0]["id"] == "qwen2.5-coder:7b"

        req = urllib.request.Request(
            f"http://127.0.0.1:{proxy_port}/v1/chat/completions",
            data=json.dumps({"model": "qwen2.5-coder:7b", "messages": []}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            payload = json.load(response)
        assert payload["choices"][0]["message"]["content"] == "model=qwen2.5-coder:7b"
    finally:
        proxy.shutdown()
        proxy.server_close()
        upstream.shutdown()
        upstream.server_close()
