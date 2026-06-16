"""Regression test for forwarding streaming request bodies.

A file-like or iterator request body must be forwarded to the real server with a
``Content-Length`` rather than chunk-encoded. ``http.client`` chunk-encodes a
file-like body when no length is known, and chunked request bodies are rejected
by some servers (including the wsgiref-based test server), which then close the
connection mid-send and surface as ``BrokenPipeError``.
"""

import http.client as httplib
import socket
import threading
from io import BytesIO

import pytest

import vcr


def _capturing_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(5)
    port = sock.getsockname()[1]
    captured = {}

    def serve():
        while True:
            try:
                conn, _ = sock.accept()
            except OSError:
                return
            try:
                buf = b""
                while b"\r\n\r\n" not in buf:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                captured.setdefault("headers", buf.split(b"\r\n\r\n")[0].decode())
                conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
                conn.close()
            except OSError:
                pass

    threading.Thread(target=serve, daemon=True).start()
    return sock, port, captured


@pytest.mark.parametrize(
    "body",
    [BytesIO(b"1234567890"), iter([b"12345", b"67890"])],
    ids=["file", "iterator"],
)
def test_streaming_body_forwarded_with_content_length(tmpdir, body):
    server_sock, port, captured = _capturing_server()
    try:
        with vcr.use_cassette(str(tmpdir.join("stream.yml"))):
            conn = httplib.HTTPConnection("127.0.0.1", port)
            conn.request("POST", "/", body=body)
            conn.getresponse()
    finally:
        server_sock.close()

    headers = captured["headers"].lower()
    assert "content-length: 10" in headers
    assert "transfer-encoding: chunked" not in headers
