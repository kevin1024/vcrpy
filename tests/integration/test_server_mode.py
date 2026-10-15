"""Server mode: the client talks to a real local HTTP server, nothing is patched."""

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pytest

import vcr
from vcr.errors import CannotOverwriteExistingCassetteException
from vcr.server import ERROR_HEADER, ERROR_STATUS


class UpstreamHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def _respond(self):
        self.server.hits.append((self.command, self.path))
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8") if length else ""
        payload = json.dumps({"method": self.command, "path": self.path, "body": body}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Set-Cookie", "a=1")
        self.send_header("Set-Cookie", "b=2")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = do_POST = do_PUT = do_DELETE = _respond


@pytest.fixture
def upstream():
    """A real HTTP server that counts the requests it receives."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
    server.hits = []
    server.url = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def get_json(url, **kwargs):
    with urlopen(Request(url, **kwargs)) as response:
        return json.loads(response.read())


def test_records_then_replays_without_hitting_upstream(tmpdir, upstream):
    path = str(tmpdir.join("cassette.yaml"))

    with vcr.use_cassette(path, base_url=upstream.url) as cass:
        first = get_json(cass.url + "/users?page=1")
        assert cass.play_count == 0
        assert len(cass) == 1
    assert upstream.hits == [("GET", "/users?page=1")]

    with vcr.use_cassette(path, base_url=upstream.url) as cass:
        second = get_json(cass.url + "/users?page=1")
        assert cass.play_count == 1
        assert cass.all_played
    assert second == first
    assert len(upstream.hits) == 1


def test_cassette_stores_the_real_uri(tmpdir, upstream):
    with vcr.use_cassette(str(tmpdir.join("c.yaml")), base_url=upstream.url) as cass:
        get_json(cass.url + "/a/b?x=1")
    assert cass.requests[0].uri == upstream.url + "/a/b?x=1"
    assert "Host" not in cass.requests[0].headers


def test_base_url_with_path_prefix(tmpdir, upstream):
    with vcr.use_cassette(str(tmpdir.join("c.yaml")), base_url=upstream.url + "/api/v1/") as cass:
        assert get_json(cass.url + "/users")["path"] == "/api/v1/users"
    assert cass.requests[0].uri == upstream.url + "/api/v1/users"


def test_request_body_is_forwarded_and_recorded(tmpdir, upstream):
    path = str(tmpdir.join("c.yaml"))
    with vcr.use_cassette(path, base_url=upstream.url, match_on=["method", "path", "body"]) as cass:
        data = get_json(cass.url + "/items", data=b'{"name": "x"}', method="POST")
    assert data == {"method": "POST", "path": "/items", "body": '{"name": "x"}'}
    assert cass.requests[0].body == b'{"name": "x"}'

    with vcr.use_cassette(path, base_url=upstream.url, match_on=["method", "path", "body"]) as cass:
        assert get_json(cass.url + "/items", data=b'{"name": "x"}', method="POST") == data
        assert cass.play_count == 1
    assert len(upstream.hits) == 1


def test_repeated_response_headers_are_replayed(tmpdir, upstream):
    path = str(tmpdir.join("c.yaml"))
    for _ in range(2):
        with vcr.use_cassette(path, base_url=upstream.url) as cass, urlopen(cass.url + "/") as response:
            assert response.headers.get_all("Set-Cookie") == ["a=1", "b=2"]
    assert len(upstream.hits) == 1


def test_json_serializer(tmpdir, upstream):
    path = str(tmpdir.join("c.json"))
    with vcr.use_cassette(path, base_url=upstream.url, serializer="json") as cass:
        get_json(cass.url + "/")
    with vcr.use_cassette(path, base_url=upstream.url, serializer="json") as cass:
        get_json(cass.url + "/")
        assert cass.play_count == 1
    assert json.loads(tmpdir.join("c.json").read())["interactions"][0]["request"]["uri"] == upstream.url + "/"


def test_fixed_port(tmpdir, upstream):
    port = free_port()
    my_vcr = vcr.VCR(base_url=upstream.url, server_port=port)
    for name in ("one.yaml", "two.yaml"):
        # The same port can be reused right away by the next cassette.
        with my_vcr.use_cassette(str(tmpdir.join(name))) as cass:
            assert cass.url == f"http://127.0.0.1:{port}"
            get_json(f"http://127.0.0.1:{port}/")


def test_server_only_runs_inside_the_cassette(tmpdir, upstream):
    context = vcr.use_cassette(str(tmpdir.join("c.yaml")), base_url=upstream.url)
    with context as cass:
        url = cass.url
        get_json(url + "/")
    assert cass.url is None
    with pytest.raises(URLError):
        urlopen(url + "/", timeout=5)


def test_nothing_is_patched_in_server_mode(tmpdir, upstream):
    with vcr.use_cassette(str(tmpdir.join("c.yaml")), base_url=upstream.url) as cass:
        # A request that bypasses the local server is neither recorded nor replayed.
        get_json(upstream.url + "/direct")
        assert len(cass) == 0
    assert upstream.hits == [("GET", "/direct")]


def test_write_protected_cassette_returns_error_and_raises_on_exit(tmpdir, upstream):
    path = str(tmpdir.join("c.yaml"))
    with vcr.use_cassette(path, base_url=upstream.url) as cass:
        get_json(cass.url + "/known")

    with (
        pytest.raises(CannotOverwriteExistingCassetteException) as excinfo,
        vcr.use_cassette(path, base_url=upstream.url) as cass,
    ):
        with pytest.raises(HTTPError) as http_error:
            urlopen(cass.url + "/unknown")
        assert http_error.value.code == ERROR_STATUS
        assert http_error.value.headers[ERROR_HEADER] == "CannotOverwriteExistingCassetteException"
        assert b"Can't overwrite existing cassette" in http_error.value.read()
    assert excinfo.value.failed_request.uri == upstream.url + "/unknown"
    assert upstream.hits == [("GET", "/known")]


def test_record_mode_none_never_reaches_upstream(tmpdir, upstream):
    with (
        pytest.raises(CannotOverwriteExistingCassetteException),
        vcr.use_cassette(str(tmpdir.join("c.yaml")), base_url=upstream.url, record_mode="none") as cass,
        pytest.raises(HTTPError),
    ):
        urlopen(cass.url + "/")
    assert upstream.hits == []


def test_new_episodes_records_new_requests(tmpdir, upstream):
    path = str(tmpdir.join("c.yaml"))
    with vcr.use_cassette(path, base_url=upstream.url) as cass:
        get_json(cass.url + "/one")
    with vcr.use_cassette(path, base_url=upstream.url, record_mode="new_episodes") as cass:
        get_json(cass.url + "/one")
        get_json(cass.url + "/two")
        assert cass.play_count == 1
    assert upstream.hits == [("GET", "/one"), ("GET", "/two")]
    with vcr.use_cassette(path, base_url=upstream.url) as cass:
        assert len(cass) == 2


def test_unreachable_upstream_is_reported(tmpdir):
    base_url = f"http://127.0.0.1:{free_port()}"
    with (
        pytest.raises(ConnectionError),
        vcr.use_cassette(str(tmpdir.join("c.yaml")), base_url=base_url) as cass,
    ):
        with pytest.raises(HTTPError) as http_error:
            urlopen(cass.url + "/")
        assert http_error.value.code == ERROR_STATUS
    assert not tmpdir.join("c.yaml").exists()


def test_decorator_with_injected_cassette(tmpdir, upstream):
    path = str(tmpdir.join("c.yaml"))

    @vcr.use_cassette(path, base_url=upstream.url, inject_cassette=True)
    def fetch(cass):
        return get_json(cass.url + "/")

    assert fetch() == fetch()
    assert len(upstream.hits) == 1


def test_works_against_httpbin(tmpdir, httpbin):
    path = str(tmpdir.join("c.yaml"))
    with vcr.use_cassette(path, base_url=httpbin.url) as cass:
        recorded = get_json(cass.url + "/get?q=1")
    with vcr.use_cassette(path, base_url=httpbin.url, record_mode="none") as cass:
        assert get_json(cass.url + "/get?q=1") == recorded
        assert cass.play_count == 1
    assert recorded["args"] == {"q": "1"}


@pytest.mark.parametrize("base_url", ["localhost:8000", "ftp://example.com", "http://example.com/?q=1"])
def test_invalid_base_url(base_url):
    with pytest.raises(ValueError, match="base_url"):
        vcr.VCR(base_url=base_url)
