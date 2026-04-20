from __future__ import annotations

import argparse
import logging
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

logger = logging.getLogger("localscript.demo_proxy")

_HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


class DemoProxyServer(ThreadingHTTPServer):
    upstream_base_url: str
    timeout_s: float


class DemoProxyHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802
        self._forward()

    def do_POST(self) -> None:  # noqa: N802
        self._forward()

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        logger.info("%s - %s", self.address_string(), format % args)

    def _forward(self) -> None:
        upstream_url = urljoin(self.server.upstream_base_url.rstrip("/") + "/", self.path.lstrip("/"))
        body = self._read_body()
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in _HOP_BY_HOP_HEADERS and key.lower() != "host"
        }
        request = Request(upstream_url, data=body, headers=headers, method=self.command)

        try:
            with urlopen(request, timeout=self.server.timeout_s) as response:
                payload = response.read()
                self.send_response(response.status)
                self._write_headers(response.headers.items(), len(payload))
                self.end_headers()
                if payload:
                    self.wfile.write(payload)
        except HTTPError as error:
            payload = error.read()
            self.send_response(error.code)
            self._write_headers(error.headers.items(), len(payload))
            self.end_headers()
            if payload:
                self.wfile.write(payload)
        except URLError as error:
            payload = f"Upstream request failed: {error}".encode("utf-8", "replace")
            self.send_response(502)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def _read_body(self) -> bytes | None:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return None
        return self.rfile.read(length)

    def _write_headers(self, headers: Iterable[tuple[str, str]], payload_len: int) -> None:
        wrote_length = False
        for key, value in headers:
            if key.lower() in _HOP_BY_HOP_HEADERS:
                continue
            if key.lower() == "content-length":
                wrote_length = True
                self.send_header(key, str(payload_len))
                continue
            self.send_header(key, value)
        if not wrote_length:
            self.send_header("Content-Length", str(payload_len))


def build_proxy_server(
    *,
    listen_host: str,
    listen_port: int,
    upstream_base_url: str,
    timeout_s: float,
) -> DemoProxyServer:
    server = DemoProxyServer((listen_host, listen_port), DemoProxyHandler)
    server.upstream_base_url = upstream_base_url
    server.timeout_s = timeout_s
    return server


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a local HTTP relay in front of a remote GPU-backed LLM endpoint for demo recording."
    )
    parser.add_argument("--listen-host", default="127.0.0.1")
    parser.add_argument("--listen-port", type=int, default=16666)
    parser.add_argument("--upstream-base-url", required=True)
    parser.add_argument("--timeout-s", type=float, default=30.0)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    server = build_proxy_server(
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        upstream_base_url=args.upstream_base_url,
        timeout_s=args.timeout_s,
    )

    host, port = server.server_address[:2]
    resolved = "unknown"
    try:
        resolved = socket.gethostbyname(socket.gethostname())
    except OSError:
        pass
    logger.info(
        "demo proxy listening on http://%s:%s -> %s (host_ip=%s)",
        host,
        port,
        args.upstream_base_url,
        resolved,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("stopping demo proxy")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
