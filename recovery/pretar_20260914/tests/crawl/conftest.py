"""A tiny local HTTP server for testing the crawler's robots.txt handling
and fetching mechanics fully offline -- deliberately not hitting real
external sites in the default test suite (unlike the live allowlist, which
is exercised manually/via the CLI and recorded in the logbook, the same
split P0-P5 already use between "pytest proves the mechanism" and "a real
run records the actual numbers").
"""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

ROBOTS_TXT = """\
User-agent: *
Disallow: /disallowed
"""

PAGE_HTML = "<html><body><p>Hello from the test server, page {n}.</p></body></html>"


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence default request logging
        pass

    def do_GET(self):
        if self.path == "/robots.txt":
            body = ROBOTS_TXT.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/disallowed"):
            body = PAGE_HTML.format(n="disallowed").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = PAGE_HTML.format(n=self.path).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


@pytest.fixture(scope="module")
def local_server():
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    thread.join(timeout=5)


def _make_mutable_handler(state: dict):
    class _MutableHandler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path == "/robots.txt":
                body = ROBOTS_TXT.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                body = state["content"].encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

    return _MutableHandler


@pytest.fixture()
def local_server_with_mutable_content():
    """A local test server whose /mutable page's content can be changed
    mid-test via the returned setter -- for proving crawl.pipeline's
    content-hash-on-re-fetch logic actually detects a real change, not
    just that it re-fetches at all. Function-scoped (unlike `local_server`)
    so each test gets a clean server, since content state is shared
    across requests to the same instance."""
    state = {"content": "initial content"}
    server = HTTPServer(("127.0.0.1", 0), _make_mutable_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]

    def set_content(content: str) -> None:
        state["content"] = f"<html><body><p>{content}</p></body></html>"

    yield f"http://127.0.0.1:{port}", set_content
    server.shutdown()
    thread.join(timeout=5)
