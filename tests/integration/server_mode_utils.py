"""Shared helpers for the server mode tests: a real upstream HTTP server and small clients."""

import base64
import contextlib
import gzip
import http.client
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import vcr

BINARY = bytes(range(256))


class UpstreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def __getattr__(self, name):
        if name.startswith("do_"):
            return self._dispatch
        raise AttributeError(name)

    def _read_body(self):
        if "chunked" in self.headers.get("Transfer-Encoding", ""):
            chunks = []
            while True:
                size = int(self.rfile.readline().strip(), 16)
                if not size:
                    self.rfile.readline()
                    return b"".join(chunks)
                chunks.append(self.rfile.read(size))
                self.rfile.readline()
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length)

    def _send(self, status=200, body=b"", headers=()):
        self.send_response(status)
        for key, value in headers:
            self.send_header(key, value)
        if status not in (204, 304):
            self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD" and status not in (204, 304):
            self.wfile.write(body)

    def _dispatch(self):
        self.server.hits.append((self.command, self.path))
        body = self._read_body()
        path = urlsplit(self.path).path
        prefix = "/prefix"
        if path.startswith(prefix):
            path = path[len(prefix) :]
            base = self.server.url + prefix
        else:
            base = self.server.url

        if path.startswith("/status/"):
            self._send(int(path.rsplit("/", 1)[1]))
        elif path == "/redirect":
            self._send(302, headers=[("Location", base + "/echo?redirected=1")])
        elif path == "/redirect-relative":
            self._send(302, headers=[("Location", urlsplit(base).path + "/echo")])
        elif path == "/gzip":
            self._send(body=gzip.compress(b"compressed payload"), headers=[("Content-Encoding", "gzip")])
        elif path == "/bytes":
            self._send(body=BINARY, headers=[("Content-Type", "application/octet-stream")])
        elif path == "/chunked":
            self.send_response(200)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            for chunk in (b"one ", b"two ", b"three"):
                self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
            self.wfile.write(b"0\r\n\r\n")
        elif path == "/cookies/set":
            cookie = (
                f"session=abc; Domain=api.example.com; Path={urlsplit(base).path or '/'}; Secure; HttpOnly"
            )
            self._send(headers=[("Set-Cookie", cookie)])
        elif path == "/slow":
            time.sleep(0.2)
            self._send(body=self.path.encode())
        elif path in ("/s3", "/s3/"):
            # Minimal S3 ListBuckets answer, enough for boto3 to parse.
            xml = (
                b'<?xml version="1.0" encoding="UTF-8"?>'
                b'<ListAllMyBucketsResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                b"<Owner><ID>owner</ID></Owner>"
                b"<Buckets><Bucket><Name>recorded-bucket</Name>"
                b"<CreationDate>2026-01-01T00:00:00.000Z</CreationDate></Bucket></Buckets>"
                b"</ListAllMyBucketsResult>"
            )
            self._send(body=xml, headers=[("Content-Type", "application/xml")])
        else:
            payload = {
                "method": self.command,
                "path": self.path,
                "body": base64.b64encode(body).decode(),
                "headers": dict(self.headers.items()),
            }
            self._send(body=json.dumps(payload).encode(), headers=[("Content-Type", "application/json")])


@contextlib.contextmanager
def upstream_server():
    """Run a real HTTP server that records the requests it receives in ``.hits``."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
    server.daemon_threads = True
    server.hits = []
    server.url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()


def connect(cass):
    parts = urlsplit(cass.url)
    return http.client.HTTPConnection(parts.hostname, parts.port, timeout=10)


def fetch(cass, method, path, body=None, headers=None, **kwargs):
    """Send one request on a fresh connection, return (status, headers, body)."""
    connection = connect(cass)
    try:
        connection.request(method, path, body=body, headers=headers or {}, **kwargs)
        response = connection.getresponse()
        return response.status, response.headers, response.read()
    finally:
        connection.close()


def record_and_replay(cassette_path, upstream, action, prefix="", **cassette_kwargs):
    """Run ``action(cass)`` while recording, then while replaying (record_mode=none).

    Returns both results and the replaying cassette.
    """
    base_url = upstream.url + prefix
    with vcr.use_cassette(cassette_path, base_url=base_url, **cassette_kwargs) as cass:
        recorded = action(cass)
    hits = len(upstream.hits)
    with vcr.use_cassette(cassette_path, base_url=base_url, record_mode="none", **cassette_kwargs) as cass:
        replayed = action(cass)
        assert cass.all_played
    assert len(upstream.hits) == hits, "replay must not reach upstream"
    return recorded, replayed, cass
