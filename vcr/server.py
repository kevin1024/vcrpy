"""Server mode: record and replay through a real local HTTP server.

Instead of patching HTTP client libraries, the client under test is pointed at
a local HTTP server.  Each incoming request is either answered from the
cassette or forwarded to the real ``base_url`` with :mod:`http.client` and
recorded.
"""

import logging
import re
import ssl
import threading
from http.client import HTTPConnection, HTTPSConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, urlunsplit

from .errors import CannotOverwriteExistingCassetteException
from .request import Request

log = logging.getLogger(__name__)

# Headers that only make sense for a single connection and must not be
# forwarded, recorded or replayed as-is.
HOP_BY_HOP_HEADERS = frozenset(
    (
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "proxy-connection",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    ),
)

# Not forwarded either: the local server already answered ``Expect: 100-continue``.
NOT_FORWARDED_HEADERS = HOP_BY_HOP_HEADERS | {"host", "expect"}

DEFAULT_PORTS = {"http": 80, "https": 443}

ERROR_STATUS = 599
ERROR_HEADER = "X-VCR-Error"


def validate_base_url(base_url):
    parts = urlsplit(base_url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"base_url must be an absolute http(s) URL, got {base_url!r}")
    if parts.query or parts.fragment:
        raise ValueError(f"base_url must not contain a query or fragment, got {base_url!r}")
    return base_url.rstrip("/")


def _build_ssl_context(verify):
    if isinstance(verify, ssl.SSLContext):
        return verify
    if verify:
        return ssl.create_default_context()
    return ssl._create_unverified_context()


def _port(parts):
    return parts.port or DEFAULT_PORTS.get(parts.scheme)


def _strip_path_prefix(path, prefix):
    """Remove ``prefix`` from ``path``; ``None`` if ``path`` is outside of it."""
    if not prefix:
        return path
    if path == prefix or path.startswith(prefix + "/"):
        return path[len(prefix) :] or "/"
    return None


_COOKIE_DOMAIN_OR_SECURE = re.compile(r";\s*(?:domain=[^;]*|secure)\s*(?=;|$)", re.IGNORECASE)
_COOKIE_PATH = re.compile(r"(;\s*path=)([^;]*)", re.IGNORECASE)


def _header_values(value):
    if isinstance(value, (list, tuple)):
        return value
    return [value]


class VCRRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def __getattr__(self, name):
        # Route every HTTP method (do_GET, do_POST, do_PROPFIND, ...) to
        # the same handler.
        if name.startswith("do_"):
            return self._handle
        raise AttributeError(name)

    def log_message(self, format, *args):
        log.debug("%s - %s", self.address_string(), format % args)

    def _read_body(self):
        if "chunked" in self.headers.get("Transfer-Encoding", "").lower():
            chunks = []
            while True:
                size_line = self.rfile.readline()
                size = int(size_line.split(b";", 1)[0].strip(), 16)
                if size == 0:
                    # Consume (and drop) trailers up to the terminating empty line.
                    while self.rfile.readline() not in (b"\r\n", b"\n", b""):
                        pass
                    break
                chunks.append(self.rfile.read(size))
                self.rfile.readline()
            return b"".join(chunks)
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else None

    def _build_vcr_request(self, body):
        headers = {}
        for key, value in self.headers.items():
            if key.lower() in NOT_FORWARDED_HEADERS:
                continue
            headers[key] = value
        uri = self.server.vcr_server.base_url + self.path
        return Request(method=self.command, uri=uri, body=body, headers=headers)

    def _handle(self):
        body = self._read_body()
        vcr_request = self._build_vcr_request(body)
        try:
            response = self.server.vcr_server.handle(vcr_request)
        except CannotOverwriteExistingCassetteException as error:
            self.server.vcr_server.cassette.errors.append(error)
            self._send_error(error)
            return
        except Exception as error:
            log.exception("Error while handling %s", vcr_request)
            self.server.vcr_server.cassette.errors.append(error)
            self._send_error(error)
            return
        self._send_recorded_response(response)

    def _send_error(self, error):
        payload = str(error).encode("utf-8")
        self.send_response_only(ERROR_STATUS, "VCR Error")
        self.send_header(ERROR_HEADER, type(error).__name__)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    def _send_recorded_response(self, response):
        status = response["status"]["code"]
        body = response["body"]["string"] or b""
        if isinstance(body, str):
            body = body.encode("utf-8")
        bodyless = self.command == "HEAD" or status in (204, 304) or 100 <= status < 200

        self.send_response_only(status, response["status"].get("message") or None)
        for key, value in response["headers"].items():
            lower = key.lower()
            if lower in HOP_BY_HOP_HEADERS:
                continue
            if lower == "content-length" and not bodyless:
                continue
            for item in _header_values(value):
                self.send_header(key, self.server.vcr_server.rewrite_response_header(lower, item))
        if not bodyless:
            self.send_header("Content-Length", str(len(body)))
        if self.close_connection:
            self.send_header("Connection", "close")
        self.end_headers()
        if not bodyless:
            self.wfile.write(body)


class _HTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._open_sockets = set()
        self._sockets_lock = threading.Lock()

    def process_request(self, request, client_address):
        with self._sockets_lock:
            self._open_sockets.add(request)
        super().process_request(request, client_address)

    def shutdown_request(self, request):
        with self._sockets_lock:
            self._open_sockets.discard(request)
        super().shutdown_request(request)

    def close_open_sockets(self):
        with self._sockets_lock:
            sockets = list(self._open_sockets)
        for sock in sockets:
            super().shutdown_request(sock)


class VCRServer:
    """A local HTTP server that replays from, or records into, a cassette."""

    def __init__(
        self,
        cassette,
        base_url,
        host="127.0.0.1",
        port=0,
        verify_upstream_ssl=True,
        upstream_timeout=None,
    ):
        self.cassette = cassette
        self.base_url = validate_base_url(base_url)
        self.host = host
        self.port = port
        self.verify_upstream_ssl = verify_upstream_ssl
        self.upstream_timeout = upstream_timeout
        self._lock = threading.Lock()
        self._httpd = None
        self._thread = None

    @property
    def url(self):
        if self._httpd is None:
            return None
        host, port = self._httpd.server_address[:2]
        if ":" in host:
            host = f"[{host}]"
        return f"http://{host}:{port}"

    def start(self):
        self._httpd = _HTTPServer((self.host, self.port), VCRRequestHandler)
        self._httpd.vcr_server = self
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            # Short poll interval so stop() returns quickly.
            kwargs={"poll_interval": 0.01},
            name=f"vcr-server-{self._httpd.server_address[1]}",
            daemon=True,
        )
        self._thread.start()
        log.debug("VCR server for %s listening on %s", self.base_url, self.url)
        return self

    def stop(self):
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd.close_open_sockets()
        self._httpd.server_close()
        self._thread.join()
        self._httpd = None
        self._thread = None

    def rewrite_response_header(self, lower_name, value):
        """Adapt a response header sent to the client so it keeps talking to us.

        The cassette always keeps the original value.
        """
        if lower_name in ("location", "content-location"):
            return self._rewrite_location(value)
        if lower_name == "set-cookie":
            return self._rewrite_set_cookie(value)
        return value

    def _rewrite_location(self, location):
        base = urlsplit(self.base_url)
        parts = urlsplit(location)
        if parts.netloc:
            scheme = parts.scheme or base.scheme
            if (scheme, parts.hostname, parts.port or DEFAULT_PORTS.get(scheme)) != (
                base.scheme,
                base.hostname,
                _port(base),
            ):
                # Points somewhere else: nothing we can proxy.
                return location
        elif not parts.path.startswith("/"):
            # Relative reference: the client resolves it against our URL.
            return location
        path = _strip_path_prefix(parts.path, base.path)
        if path is None:
            return location
        relative = urlunsplit(("", "", path, parts.query, parts.fragment))
        return self.url + relative if parts.netloc else relative

    def _rewrite_set_cookie(self, value):
        # Domain and Secure would stop clients from sending the cookie back to
        # http://127.0.0.1:<port>.
        value = _COOKIE_DOMAIN_OR_SECURE.sub("", value)
        prefix = urlsplit(self.base_url).path

        def rewrite_path(match):
            path = _strip_path_prefix(match.group(2).strip(), prefix)
            return match.group(1) + (path if path is not None else match.group(2))

        return _COOKIE_PATH.sub(rewrite_path, value)

    def handle(self, vcr_request):
        cassette = self.cassette
        with self._lock:
            if cassette.can_play_response_for(vcr_request):
                log.info("Playing response for %s from cassette", vcr_request)
                return cassette.play_response(vcr_request)
            if cassette.write_protected and cassette.filter_request(vcr_request):
                raise CannotOverwriteExistingCassetteException(
                    cassette=cassette,
                    failed_request=vcr_request,
                )

        log.info("%s not in cassette, sending to real server", vcr_request)
        response = self.forward(vcr_request)
        with self._lock:
            cassette.append(vcr_request, response)
        return response

    def forward(self, vcr_request):
        parts = vcr_request.parsed_uri
        if parts.scheme == "https":
            # Bound at import time, so an enclosing patch-mode cassette (which
            # replaces http.client.HTTPConnection) never intercepts forwarding.
            connection = HTTPSConnection(
                parts.hostname,
                parts.port,
                timeout=self.upstream_timeout,
                context=_build_ssl_context(self.verify_upstream_ssl),
            )
        else:
            connection = HTTPConnection(parts.hostname, parts.port, timeout=self.upstream_timeout)
        selector = parts.path or "/"
        if parts.query:
            selector += "?" + parts.query
        try:
            connection.request(
                vcr_request.method,
                selector,
                body=vcr_request.body,
                headers=dict(vcr_request.headers),
            )
            upstream = connection.getresponse()
            body = upstream.read()
            headers = {}
            for key, value in upstream.getheaders():
                headers.setdefault(key, []).append(value)
            return {
                "status": {"code": upstream.status, "message": upstream.reason},
                "headers": headers,
                "body": {"string": body},
            }
        finally:
            connection.close()
