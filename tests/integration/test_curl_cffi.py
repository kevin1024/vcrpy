import asyncio
import json
import os
import subprocess
import sys
import threading
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from urllib.parse import parse_qs, urlsplit

import pytest

import vcr
from vcr.errors import CannotOverwriteExistingCassetteException

curl_requests = pytest.importorskip("curl_cffi.requests")


@pytest.fixture
def origin():
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            path = urlsplit(self.path).path
            hits.append(
                {"path": self.path, "method": self.command, "body": body, "headers": dict(self.headers)},
            )
            payload = {
                "/empty": b"",
                "/binary": b"\x00\xff\x80\r\nend",
                "/text": "na\u00efve\nsecond\r\nlast".encode(),
            }.get(
                path,
                json.dumps({"path": path, "cookie": self.headers.get("Cookie", ""), "ok": True}).encode(),
            )
            if path == "/disconnect":
                self.close_connection = True
                return
            status, reason = {
                "/redirect": (302, "Found"),
                "/error": (409, "Conflict"),
                "/boundary-ok": (399, "Upper Success"),
                "/boundary-error": (400, "Lower Error"),
                "/latin": (200, "Alternate"),
            }.get(path, (200, "Fine"))
            if path == "/latin":
                payload = b"ol\xe1"
            self.send_response(status, reason)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header(
                "Content-Type",
                "text/plain; charset=iso-8859-1"
                if path == "/latin"
                else "text/plain; charset=utf-8"
                if path in ("/empty", "/binary", "/text")
                else "application/json",
            )
            self.send_header("X-Repeated", "first")
            self.send_header("X-Repeated", "second")
            if path == "/redirect":
                self.send_header("Location", "/final?landed=yes")
            if path == "/ip-domain-cookie":
                self.send_header("Set-Cookie", "identity=one; Domain=127.0.0.1; Path=/")
            if path == "/ip-delete-cookie":
                self.send_header("Set-Cookie", "identity=; Max-Age=0; Path=/")
            if path == "/scope/set":
                self.send_header("Set-Cookie", "scoped=yes; Path=/scope")
                self.send_header("Set-Cookie", 'quoted=new; Path="/scope"')
                self.send_header("Set-Cookie", "foreign=no; Domain=example.invalid; Path=/")
            if path == "/scope/delete":
                self.send_header("Set-Cookie", 'quoted=gone; Path="/scope"; Max-Age=0')
            if path == "/secret":
                self.send_header("Set-Cookie", "secret=hidden; Path=/")
                self.send_header("Set-Cookie", "allowed=ok; Path=/")
                self.send_header("X-Secret", "hidden")
            if path in ("/replace-cookie", "/sub/replace-cookie"):
                self.send_header("Set-Cookie", "x=new; Domain=localhost; Path=/")
                self.send_header("Set-Cookie", 'token="quoted"; Domain=localhost; Path=/')
                self.send_header("Set-Cookie", "flag; Domain=localhost; Path=/")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(payload)

        do_POST = do_GET
        do_PUT = do_GET
        do_PATCH = do_GET
        do_DELETE = do_GET
        do_HEAD = do_GET
        do_OPTIONS = do_GET

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}", hits
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


class Client:
    def __init__(self, kind, **options):
        self.kind = kind
        self.options = options

    def __enter__(self):
        if self.kind == "async":
            self.loop = asyncio.new_event_loop()
            self.session = curl_requests.AsyncSession(**self.options)
        else:
            self.session = curl_requests.Session(**self.options)
        return self

    def __exit__(self, *args):
        if self.kind == "async":
            self.loop.run_until_complete(self.session.close())
            self.loop.close()
        else:
            self.session.close()

    def request(self, method, url, **options):
        result = self.session.request(method, url, timeout=3, **options)
        return self.loop.run_until_complete(result) if self.kind == "async" else result

    def content(self, response, stream):
        if not stream:
            return response.content
        if self.kind == "async":

            async def read():
                return b"".join([part async for part in response.aiter_content()])

            return self.loop.run_until_complete(read())
        return b"".join(response.iter_content())

    def close_response(self, response):
        for _ in range(2):
            if self.kind == "async":
                self.loop.run_until_complete(response.aclose())
            else:
                response.close()

    def stream_lines(self, url):
        if self.kind == "async":

            async def read():
                async with self.session.stream("GET", url, timeout=3) as response:
                    return [line async for line in response.aiter_lines()]

            return self.loop.run_until_complete(read())
        with self.session.stream("GET", url, timeout=3) as response:
            return list(response.iter_lines())


@pytest.mark.parametrize("kind", ["sync", "async"])
@pytest.mark.parametrize("body_kind", ["none", "raw", "form", "json"])
@pytest.mark.parametrize("stream", [False, True], ids=["buffered", "stream"])
def test_native_roundtrip(kind, body_kind, stream, origin, tmp_path):
    base, hits = origin
    cases = {
        "none": ("GET", "/empty", {}, {}, b""),
        "raw": (
            "POST",
            "/binary",
            {"data": b"\x00\xffpayload"},
            {"data": b"\x00\xffpayload"},
            b"\x00\xff\x80\r\nend",
        ),
        "form": (
            "POST",
            "/text",
            {"data": {"a": "one", "b": "two"}},
            {"data": {"b": "two", "a": "one"}},
            "na\u00efve\nsecond\r\nlast".encode(),
        ),
        "json": (
            "PUT",
            "/json",
            {"json": {"a": 1, "b": [2]}},
            {"json": {"b": [2], "a": 1}},
            b'{"path": "/json", "cookie": "", "ok": true}',
        ),
    }
    method, path, first, second, expected = cases[body_kind]
    cassette_path = str(tmp_path / "roundtrip.yaml")
    options = {
        "base_url": base,
        "params": {"base": "one", "replace": "old"},
        "headers": {"X-Session": "yes", "X-Override": "old"},
    }
    recorder = vcr.VCR(match_on=["method", "uri", "body", "headers"])
    for replay, body_options in [(False, first), (True, second)]:
        with Client(kind, **options) as client, recorder.use_cassette(cassette_path) as cassette:
            request_options = {
                "params": {"replace": "new", "tag": ["a", "b"]},
                "headers": {"X-Override": "new"},
                "stream": stream,
            }
            request_options.update(body_options)
            response = client.request(method, path, **request_options)
            assert len(cassette) == 1
            assert response.status_code == 200
            assert response.reason == "Fine"
            assert response.headers.get_list("X-Repeated") == ["first", "second"]
            assert urlsplit(response.url).path == path
            assert parse_qs(urlsplit(response.url).query) == {
                "base": ["one"],
                "replace": ["new"],
                "tag": ["a", "b"],
            }
            assert client.content(response, stream) == expected
            if not stream and body_kind == "json":
                assert response.json() == {"path": "/json", "cookie": "", "ok": True}
            if not stream and body_kind == "form":
                assert response.text == "na\u00efve\nsecond\r\nlast"
            response.raise_for_status()
            client.close_response(response)
            request = cassette.requests[0]
            assert request.headers["X-Session"] == "yes"
            assert request.headers["X-Override"] == "new"
            if "Content-Type" in hits[0]["headers"]:
                assert request.headers["Content-Type"] == hits[0]["headers"]["Content-Type"]
            assert len(hits) == 1
            assert cassette.play_count == int(replay)
            if replay and body_kind != "none":
                changed = {
                    "raw": {"data": b"different"},
                    "form": {"data": {"a": "changed", "b": "two"}},
                    "json": {"json": {"a": 99, "b": [2]}},
                }[body_kind]
                cassette.rewind()
                request_options.update(changed)
                with pytest.raises(CannotOverwriteExistingCassetteException):
                    client.request(method, path, **request_options)
                assert len(hits) == 1


@pytest.mark.parametrize("kind", ["sync", "async"])
@pytest.mark.parametrize("mode", ["once", "none", "all", "new_episodes"])
def test_record_modes(kind, mode, origin, tmp_path):
    base, hits = origin
    path = str(tmp_path / "modes.yaml")
    with Client(kind) as client:
        with vcr.use_cassette(path) as cassette:
            client.request("GET", base + "/first")
            assert len(cassette) == 1
        with vcr.use_cassette(path, record_mode=mode) as cassette:
            client.request("GET", base + "/first")
            assert len(hits) == (2 if mode == "all" else 1)
            if mode in ("none", "once"):
                with pytest.raises(CannotOverwriteExistingCassetteException):
                    client.request("GET", base + "/second")
                assert len(hits) == 1
            else:
                client.request("GET", base + "/second")
                assert len(hits) == (3 if mode == "all" else 2)
                assert len(cassette) == (3 if mode == "all" else 2)


@pytest.mark.parametrize("kind", ["sync", "async"])
def test_consumption_and_repeat(kind, origin, tmp_path):
    base, hits = origin
    path = str(tmp_path / "repeat.yaml")
    with Client(kind) as client:
        with vcr.use_cassette(path) as cassette:
            client.request("GET", base + "/json")
            assert len(cassette) == 1
        with vcr.use_cassette(path) as cassette:
            client.request("GET", base + "/json")
            assert cassette.all_played
            with pytest.raises(CannotOverwriteExistingCassetteException):
                client.request("GET", base + "/json")
            cassette.rewind()
            client.request("GET", base + "/json")
        with vcr.use_cassette(path, allow_playback_repeats=True) as cassette:
            for _ in range(3):
                assert client.request("GET", base + "/json").json()["ok"] is True
            assert cassette.play_count == 3
    assert len(hits) == 1


@pytest.mark.parametrize("kind", ["sync", "async"])
def test_filters_and_cookie_redaction(kind, origin, tmp_path):
    base, hits = origin
    path = str(tmp_path / "filtered.yaml")

    def filter_request(request):
        return None if request.path == "/bypass" else request

    def filter_response(response):
        response["headers"] = {
            name: (["allowed=ok; Path=/"] if name.lower() == "set-cookie" else values)
            for name, values in response["headers"].items()
            if name.lower() != "x-secret"
        }
        return response

    recorder = vcr.VCR(
        before_record_request=filter_request,
        before_record_response=filter_response,
        filter_headers=[("X-Secret", "REDACTED")],
    )
    with Client(kind) as client, recorder.use_cassette(path) as cassette:
        client.request("GET", base + "/secret", headers={"X-Secret": "hidden"})
        assert len(cassette) == 1
        assert cassette.requests[0].headers["X-Secret"] == "REDACTED"
    with Client(kind) as client, recorder.use_cassette(path, record_mode="none") as cassette:
        response = client.request("GET", base + "/secret", headers={"X-Secret": "different"})
        assert "X-Secret" not in response.headers
        assert dict(response.cookies) == {"allowed": "ok"}
        assert dict(client.session.cookies) == {"allowed": "ok"}
        assert len(hits) == 1
        client.request("GET", base + "/bypass")
        assert len(hits) == 2
        assert len(cassette) == 1
        assert "allowed=ok" in hits[-1]["headers"].get("Cookie", "")
    assert "hidden" not in (tmp_path / "filtered.yaml").read_text()


@pytest.mark.parametrize("kind", ["sync", "async"])
@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_replayed_cookie_domain_and_path(kind, host, origin, tmp_path):
    base, hits = origin
    base = base.replace("127.0.0.1", host)
    path = str(tmp_path / "cookies.yaml")
    deletion_path = str(tmp_path / "deleted-cookies.yaml")
    for replay in (False, True):
        before = len(hits)
        with Client(kind) as client:
            client.session.cookies.set("quoted", "old", domain=host, path="/scope")
            with vcr.use_cassette(path) as cassette:
                response = client.request("GET", base + "/scope/set")
                assert len(cassette) == 1
                assert response.cookies.get("scoped") == "yes"
                quoted = [
                    (cookie.value, cookie.path)
                    for cookie in client.session.cookies.jar
                    if cookie.name == "quoted"
                ]
                assert quoted == [("new", "/scope")]
            assert len(hits) == before + int(not replay)
            scope_cookie = client.request("GET", base + "/scope/echo").json()["cookie"]
            assert set(scope_cookie.split("; ")) == {"scoped=yes", "quoted=new"}
            assert client.request("GET", base + "/outside").json()["cookie"] == ""
            assert "foreign" not in dict(client.session.cookies)
            with vcr.use_cassette(deletion_path) as cassette:
                client.request("GET", base + "/scope/delete")
                assert len(cassette) == 1
                assert client.session.cookies.get("quoted") is None
            assert client.request("GET", base + "/scope/echo").json()["cookie"] == "scoped=yes"
            assert len(hits) == before + 3 + 2 * int(not replay)


@pytest.mark.parametrize("kind", ["sync", "async"])
@pytest.mark.parametrize("host,secure", [("localhost", False), ("127.0.0.1", True)])
def test_effective_cookie_headers(kind, host, secure, origin, tmp_path):
    base, hits = origin
    base = base.replace("127.0.0.1", host)
    path = str(tmp_path / "cookie-headers.yaml")
    for replay in (False, True):
        with (
            Client(kind) as client,
            vcr.use_cassette(path, match_on=["method", "uri", "headers"]) as cassette,
        ):
            client.session.cookies.set("session", "yes", domain=host, path="/", secure=secure)
            client.request("GET", base + "/json", cookies={"request": "ok"})
            assert len(cassette) == 1
            wire = hits[0]["headers"]["Cookie"]
            assert "session=yes" in wire
            recorded_cookies = cassette.requests[0].headers.get("Cookie", "")
            assert set(recorded_cookies.split("; ")) == set(wire.split("; "))
            assert len(hits) == 1
            assert cassette.play_count == int(replay)


@pytest.mark.parametrize("kind", ["sync", "async"])
def test_stream_context_lines(kind, origin, tmp_path):
    base, hits = origin
    path = str(tmp_path / "lines.yaml")
    for _ in range(2):
        with Client(kind) as client, vcr.use_cassette(path) as cassette:
            assert client.stream_lines(base + "/text") == ["na\u00efve".encode(), b"second", b"last"]
            assert len(cassette) == 1
    assert len(hits) == 1


@pytest.mark.parametrize("kind", ["sync", "async"])
def test_nested_exception_restores_requests(kind, origin, tmp_path):
    base, hits = origin
    outer_path = str(tmp_path / "outer.yaml")
    inner_path = str(tmp_path / "inner.yaml")
    for replay in (False, True):
        with Client(kind) as client:
            with pytest.raises(RuntimeError, match="outer exit"), vcr.use_cassette(outer_path) as outer:
                client.request("GET", base + "/first")
                assert len(outer) == (2 if replay else 1)
                with pytest.raises(RuntimeError, match="nested exit"), vcr.use_cassette(inner_path) as inner:
                    client.request("GET", base + "/inner")
                    assert len(inner) == 1
                    raise RuntimeError("nested exit")
                client.request("GET", base + "/last")
                assert len(outer) == 2
                raise RuntimeError("outer exit")
            before = len(hits)
            assert client.request("GET", base + "/outside").json()["path"] == "/outside"
            assert len(hits) == before + 1
    assert len(hits) == 5


@pytest.mark.parametrize("kind", ["sync", "async"])
def test_httpx_curl_single_interactions(kind, origin, tmp_path):
    import httpx
    from httpx_curl_cffi import AsyncCurlTransport, CurlTransport

    base, hits = origin
    path = str(tmp_path / "coexist.yaml")
    for replay in (False, True):
        with Client(kind) as client, vcr.use_cassette(path) as cassette:
            client.request("GET", base + "/native")
            assert len(cassette) >= 1
            if kind == "async":

                async def fetch(replay=replay):
                    async with httpx.AsyncClient(transport=AsyncCurlTransport()) as transport_client:
                        response = await transport_client.get(base + "/httpx")
                        if not replay:
                            with pytest.raises(httpx.RequestError):
                                await transport_client.get(base + "/disconnect")
                        assert len(cassette) == (3 if replay else 2)
                        last = await client.session.request("GET", base + "/last", timeout=3)
                        assert last.json()["path"] == "/last"
                        assert len(cassette) == 3
                        return response

                response = client.loop.run_until_complete(fetch())
            else:
                with httpx.Client(transport=CurlTransport()) as transport_client:
                    response = transport_client.get(base + "/httpx")
                    if not replay:
                        with pytest.raises(httpx.RequestError):
                            transport_client.get(base + "/disconnect")
                assert len(cassette) == (3 if replay else 2)
                client.request("GET", base + "/last")
            assert response.json()["path"] == "/httpx"
            assert len(cassette) == 3
    assert len(hits) == 4


def test_module_request_helpers(origin, tmp_path):
    base, hits = origin
    path = str(tmp_path / "module.yaml")
    methods = [
        ("get", curl_requests.get),
        ("post", curl_requests.post),
        ("put", curl_requests.put),
        ("patch", curl_requests.patch),
        ("delete", curl_requests.delete),
        ("head", curl_requests.head),
        ("options", curl_requests.options),
        ("get", partial(curl_requests.request, "GET")),
    ]
    for replay in (False, True):
        with vcr.use_cassette(path) as cassette:
            for index, (method, request) in enumerate(methods, 1):
                response = request(base + "/json", timeout=3)
                assert len(cassette) == (len(methods) if replay else index)
                assert response.status_code == 200
                if method == "head":
                    assert response.content == b""
                else:
                    assert response.json()["ok"] is True
    assert len(hits) == len(methods)


@pytest.mark.parametrize("kind", ["sync", "async"])
@pytest.mark.parametrize(
    "endpoint,status,reason",
    [
        ("/error", 409, "Conflict"),
        ("/boundary-ok", 399, "Upper Success"),
        ("/boundary-error", 400, "Lower Error"),
    ],
)
def test_http_error_response(kind, endpoint, status, reason, origin, tmp_path):
    base, hits = origin
    path = str(tmp_path / "error.yaml")
    for _ in range(2):
        with Client(kind) as client, vcr.use_cassette(path) as cassette:
            response = client.request("GET", base + endpoint)
            assert len(cassette) == 1
            assert response.status_code == status
            assert response.reason == reason
            if status >= 400:
                with pytest.raises(curl_requests.exceptions.HTTPError):
                    response.raise_for_status()
            else:
                response.raise_for_status()
    assert len(hits) == 1


def test_optional_integration_absence(origin, tmp_path):
    base, hits = origin
    with curl_requests.Session() as client, vcr.use_cassette(str(tmp_path / "native.yaml")) as cassette:
        client.get(base + "/native", timeout=3)
        assert len(cassette) == 1
    program = "\n".join(
        [
            "import importlib.abc",
            "import sys",
            "",
            "class BlockCurl(importlib.abc.MetaPathFinder):",
            "    def find_spec(self, fullname, path=None, target=None):",
            "        if fullname.split('.')[0] in {'curl_cffi', 'httpx_curl_cffi'}:",
            "            raise ImportError('optional curl integration is unavailable')",
            "",
            "sys.meta_path.insert(0, BlockCurl())",
            "import vcr",
            "import urllib.request",
            "for _ in range(2):",
            "    with vcr.use_cassette(sys.argv[2]) as cassette:",
            "        with urllib.request.urlopen(sys.argv[1], timeout=3) as response:",
            "            assert response.status == 200",
            "            assert b'\"ok\": true' in response.read()",
            "        assert len(cassette) == 1",
            "assert 'curl_cffi' not in sys.modules",
            "assert 'httpx_curl_cffi' not in sys.modules",
        ],
    )
    result = subprocess.run(
        [sys.executable, "-c", program, base + "/stdlib", str(tmp_path / "stdlib.yaml")],
        cwd=tmp_path,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(hits) == 2


@pytest.mark.parametrize("kind", ["sync", "async"])
@pytest.mark.parametrize("method", ["POST", "PUT"])
def test_empty_body_matching(kind, method, origin, tmp_path):
    base, hits = origin
    path = str(tmp_path / "empty-request.yaml")
    for replay in (False, True):
        with Client(kind) as client, vcr.use_cassette(path, match_on=["method", "uri", "body"]) as cassette:
            response = client.request(method, base + "/json")
            assert len(cassette) == 1
            assert response.json()["ok"] is True
            assert cassette.play_count == int(replay)
            assert len(hits) == 1


@pytest.mark.parametrize("kind", ["sync", "async"])
def test_standard_response_charset_and_unread_close(kind, origin, tmp_path):
    base, hits = origin
    path = str(tmp_path / "standard.yaml")

    def without_url(response):
        response.pop("url", None)
        return response

    for replay in (False, True):
        with Client(kind) as client, vcr.use_cassette(path, before_record_response=without_url) as cassette:
            response = client.request("GET", base + "/latin")
            assert len(cassette) == (2 if replay else 1)
            assert response.url == base + "/latin"
            assert response.reason == "Alternate"
            assert response.content == b"ol\xe1"
            assert response.text == "ol\u00e1"
            assert "url" not in cassette.responses[0]
            unread = client.request("GET", base + "/binary", stream=True)
            assert len(cassette) == 2
            client.close_response(unread)
            assert unread.status_code == 200
    assert len(hits) == 2


@pytest.mark.parametrize("kind", ["sync", "async"])
def test_cookie_replacement_preserves_other_entries(kind, origin, tmp_path):
    base, hits = origin
    base = base.replace("127.0.0.1", "localhost")
    for endpoint in ("/replace-cookie", "/sub/replace-cookie"):
        path = str(tmp_path / (endpoint.replace("/", "-") + ".yaml"))
        for _ in range(2):
            with Client(kind) as client, vcr.use_cassette(path) as cassette:
                client.session.cookies.set("x", "old", domain="localhost", path="/")
                client.session.cookies.set("unrelated", "keep", domain="other.invalid", path="/")
                client.session.cookies.set("flag", "keep", domain=".localhost", path="/")
                client.request("GET", base + endpoint)
                assert len(cassette) == 1
                replacements = [cookie.value for cookie in client.session.cookies.jar if cookie.name == "x"]
                assert replacements == ["new"]
                assert client.session.cookies.get("token") == "quoted"
                assert client.session.cookies.get("unrelated") == "keep"
                assert client.session.cookies.get("flag") == "keep"
    assert len(hits) == 2


@pytest.mark.parametrize("kind", ["sync", "async"])
@pytest.mark.parametrize(
    "source",
    [
        "content-bytes",
        "data-file",
        "content-file",
        "data-str",
        "content-str",
        "data-empty-bytes",
    ],
)
def test_raw_upload_matching_and_bypass(kind, source, origin, tmp_path):
    base, hits = origin
    path = str(tmp_path / "upload.yaml")

    value = (
        b""
        if "-empty-" in source
        else "a=na\u00efve\u2603".encode()
        if source.endswith("-str")
        else b"a=first"
    )
    different = "a=th\u00e9\u2603".encode() if source.endswith("-str") else b"a=other"

    def upload(value):
        if source.endswith("-str"):
            return {source.split("-")[0]: value.decode()}
        if source.endswith("-bytes"):
            return {source.split("-")[0]: value}
        body = BytesIO(b"prefix" + value)
        body.seek(6)
        return {source.split("-")[0]: body}

    def filter_request(request):
        return None if request.path == "/bypass" else request

    recorder = vcr.VCR(match_on=["method", "uri", "body"], before_record_request=filter_request)
    with Client(kind) as client:
        with recorder.use_cassette(path) as cassette:
            client.request("POST", base + "/upload", **upload(value))
            assert len(cassette) == 1
            assert hits[0]["body"] == value
            recorded_body = cassette.requests[0].body
            if isinstance(recorded_body, BytesIO):
                recorded_body = recorded_body.read()
            if value:
                assert recorded_body == value
            else:
                assert recorded_body in (None, b"")
            assert cassette.requests[0].headers.get("Content-Type") == hits[0]["headers"].get("Content-Type")
        with recorder.use_cassette(path, record_mode="none") as cassette:
            assert client.request("POST", base + "/upload", **upload(value)).status_code == 200
            assert len(hits) == 1
            cassette.rewind()
            with pytest.raises(CannotOverwriteExistingCassetteException):
                client.request("POST", base + "/upload", **upload(different))
            assert len(hits) == 1
            client.request("POST", base + "/bypass", **upload(value))
            assert len(hits) == 2
            assert hits[-1]["body"] == value
            assert len(cassette) == 1


@pytest.mark.parametrize("kind", ["sync", "async"])
def test_distinct_effective_match_dimensions(kind, origin, tmp_path):
    base, hits = origin
    path = str(tmp_path / "dimensions.yaml")
    options = {
        "params": {"q": "one"},
        "headers": {"X-Match": "one", "Expect": "100-continue"},
        "cookies": {"mode": "one"},
        "auth": ("request", "secret"),
        "referer": base + "/ref-one",
    }
    recorder = vcr.VCR(match_on=["method", "uri", "headers"])
    with Client(kind, auth=("session", "secret")) as client:
        with recorder.use_cassette(path) as cassette:
            client.request("GET", base + "/json", **options)
            assert len(cassette) == 1
            assert cassette.requests[0].headers["Authorization"] == "Basic cmVxdWVzdDpzZWNyZXQ="
            assert cassette.requests[0].headers["Referer"] == base + "/ref-one"
            assert "Expect" not in hits[0]["headers"]
        options["headers"]["Expect"] = "different"
        with recorder.use_cassette(path, record_mode="none") as cassette:
            assert client.request("GET", base + "/json", **options).status_code == 200
            changes = [
                ("HEAD", {}),
                ("GET", {"params": {"q": "two"}}),
                ("GET", {"headers": {"X-Match": "two"}}),
                ("GET", {"cookies": {"mode": "two"}}),
                ("GET", {"auth": ("different", "secret")}),
                ("GET", {"referer": base + "/ref-two"}),
            ]
            for method, change in changes:
                cassette.rewind()
                changed = dict(options)
                changed.update(change)
                with pytest.raises(CannotOverwriteExistingCassetteException):
                    client.request(method, base + "/json", **changed)
                assert len(hits) == 1


@pytest.mark.parametrize("kind", ["sync", "async"])
def test_redirect_response_url(kind, origin, tmp_path):
    base, hits = origin
    path = str(tmp_path / "redirect.yaml")
    for replay in (False, True):
        with Client(kind) as client, vcr.use_cassette(path) as cassette:
            response = client.request("GET", base + "/redirect")
            assert response.status_code == 200
            assert response.url == base + "/final?landed=yes"
            assert response.json()["path"] == "/final"
            assert len(cassette) == 1
            assert cassette.play_count == int(replay)
            assert len(hits) == 2


@pytest.mark.parametrize("kind", ["sync", "async"])
def test_ip_cookie_identity_deletion(kind, origin, tmp_path):
    base, hits = origin
    path = str(tmp_path / "ip-cookie.yaml")
    for replay in (False, True):
        with Client(kind) as client, vcr.use_cassette(path) as cassette:
            client.session.cookies.set("unrelated", "keep", domain="other.invalid", path="/")
            client.request("GET", base + "/ip-domain-cookie")
            assert client.session.cookies.get("identity") == "one"
            client.request("GET", base + "/ip-delete-cookie")
            assert client.session.cookies.get("identity") is None
            assert client.session.cookies.get("unrelated") == "keep"
            assert len(cassette) == 2
            assert cassette.play_count == 2 * int(replay)
            assert len(hits) == 2
