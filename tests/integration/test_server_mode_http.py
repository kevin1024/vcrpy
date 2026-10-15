"""Server mode: HTTP protocol details (bodies, methods, redirects, encodings, connections)."""

import base64
import gzip
import http.cookiejar
import json
import ssl
import threading
import time
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, build_opener, urlopen

import pytest

import vcr
from vcr.errors import CannotOverwriteExistingCassetteException
from vcr.server import ERROR_STATUS

from .server_mode_utils import BINARY, connect, fetch, record_and_replay, upstream_server


@pytest.fixture
def upstream():
    with upstream_server() as server:
        yield server


@pytest.fixture
def cassette_path(tmpdir):
    return str(tmpdir.join("cassette.yaml"))


@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def test_methods(cassette_path, upstream, method):
    def action(cass):
        status, _, body = fetch(cass, method, "/echo", body=b"payload")
        return status, json.loads(body)

    recorded, replayed, _ = record_and_replay(cassette_path, upstream, action)
    assert recorded == replayed
    assert recorded[1]["method"] == method
    assert base64.b64decode(recorded[1]["body"]) == b"payload"


def test_head_keeps_content_length_and_sends_no_body(cassette_path, upstream):
    def action(cass):
        connection = connect(cass)
        connection.request("HEAD", "/bytes")
        head = connection.getresponse()
        assert head.read() == b""
        # The connection is still usable, so no stray body bytes were sent.
        connection.request("GET", "/bytes")
        assert connection.getresponse().read() == BINARY
        connection.close()
        return head.status, head.headers["Content-Length"]

    recorded, replayed, _ = record_and_replay(cassette_path, upstream, action)
    assert recorded == replayed == (200, "256")


@pytest.mark.parametrize("status", [204, 304])
def test_bodyless_statuses(cassette_path, upstream, status):
    def action(cass):
        connection = connect(cass)
        connection.request("GET", f"/status/{status}")
        response = connection.getresponse()
        assert response.read() == b""
        connection.request("GET", "/echo")
        assert connection.getresponse().status == 200
        connection.close()
        return response.status

    recorded, replayed, _ = record_and_replay(cassette_path, upstream, action)
    assert recorded == replayed == status


@pytest.mark.parametrize("status", [400, 404, 500, 503])
def test_error_statuses_are_recorded(cassette_path, upstream, status):
    def action(cass):
        with pytest.raises(HTTPError) as error:
            urlopen(cass.url + f"/status/{status}")
        return error.value.code

    recorded, replayed, _ = record_and_replay(cassette_path, upstream, action)
    assert recorded == replayed == status


def test_chunked_request_body(cassette_path, upstream):
    def action(cass):
        chunks = iter([b"first,", b"second,", b"third"])
        _, _, body = fetch(cass, "POST", "/echo", body=chunks, encode_chunked=True)
        return base64.b64decode(json.loads(body)["body"])

    recorded, replayed, _ = record_and_replay(
        cassette_path,
        upstream,
        action,
        match_on=["method", "path", "body"],
    )
    assert recorded == replayed == b"first,second,third"
    with vcr.use_cassette(cassette_path, base_url=upstream.url) as cass:
        assert cass.requests[0].body == b"first,second,third"
        assert "Transfer-Encoding" not in cass.requests[0].headers


def test_binary_bodies(cassette_path, upstream):
    def action(cass):
        _, _, echoed = fetch(cass, "POST", "/echo", body=BINARY)
        _, _, downloaded = fetch(cass, "GET", "/bytes")
        return base64.b64decode(json.loads(echoed)["body"]), downloaded

    recorded, replayed, _ = record_and_replay(cassette_path, upstream, action)
    assert recorded == replayed == (BINARY, BINARY)


def test_empty_body_post(cassette_path, upstream):
    def action(cass):
        return json.loads(fetch(cass, "POST", "/echo", body=b"")[2])["body"]

    recorded, replayed, _ = record_and_replay(cassette_path, upstream, action)
    assert recorded == replayed == ""


def test_chunked_response_is_replayed_with_content_length(cassette_path, upstream):
    def action(cass):
        _, headers, body = fetch(cass, "GET", "/chunked")
        assert headers["Transfer-Encoding"] is None
        assert headers["Content-Length"] == str(len(body))
        return body

    recorded, replayed, _ = record_and_replay(cassette_path, upstream, action)
    assert recorded == replayed == b"one two three"


def test_gzip_body_is_replayed_byte_identical(cassette_path, upstream):
    def action(cass):
        _, headers, body = fetch(cass, "GET", "/gzip", headers={"Accept-Encoding": "gzip"})
        assert headers["Content-Encoding"] == "gzip"
        return body

    recorded, replayed, _ = record_and_replay(cassette_path, upstream, action)
    assert recorded == replayed
    assert gzip.decompress(replayed) == b"compressed payload"


def test_decode_compressed_response(cassette_path, upstream):
    with vcr.use_cassette(cassette_path, base_url=upstream.url, decode_compressed_response=True) as cass:
        fetch(cass, "GET", "/gzip", headers={"Accept-Encoding": "gzip"})
    with vcr.use_cassette(cassette_path, base_url=upstream.url, record_mode="none") as cass:
        _, headers, body = fetch(cass, "GET", "/gzip", headers={"Accept-Encoding": "gzip"})
    assert body == b"compressed payload"
    assert headers["Content-Encoding"] is None
    assert headers["Content-Length"] == str(len(body))


@pytest.mark.parametrize("prefix", ["", "/prefix"])
@pytest.mark.parametrize("route", ["/redirect", "/redirect-relative"])
def test_redirects_stay_on_the_local_server(cassette_path, upstream, prefix, route):
    def action(cass):
        with urlopen(cass.url + route) as response:
            assert response.url.startswith(cass.url)
            return json.loads(response.read())["path"]

    recorded, replayed, cass = record_and_replay(cassette_path, upstream, action, prefix=prefix)
    assert recorded == replayed
    assert recorded.startswith(prefix + "/echo")
    assert cass.play_count == 2
    # The cassette keeps the original Location sent by upstream.
    location = cass.responses[0]["headers"]["Location"][0]
    assert location == (
        upstream.url + prefix + "/echo?redirected=1" if route == "/redirect" else prefix + "/echo"
    )


@pytest.mark.parametrize("prefix", ["", "/prefix"])
def test_cookies_are_sent_back_to_the_local_server(tmpdir, upstream, prefix):
    path = str(tmpdir.join("c.yaml"))
    for record_mode in ("once", "none"):
        opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        with vcr.use_cassette(path, base_url=upstream.url + prefix, record_mode=record_mode) as cass:
            opener.open(cass.url + "/cookies/set").read()
            echoed = json.loads(opener.open(cass.url + "/echo").read())
        assert echoed["headers"]["Cookie"] == "session=abc"
    recorded_cookie = cass.responses[0]["headers"]["Set-Cookie"][0]
    assert "Domain=api.example.com" in recorded_cookie
    assert "Secure" in recorded_cookie


def test_keep_alive_connection_serves_many_requests(cassette_path, upstream):
    def action(cass):
        connection = connect(cass)
        bodies = []
        for i in range(5):
            connection.request("POST", f"/echo?i={i}", body=b"x" * i)
            bodies.append(json.loads(connection.getresponse().read())["path"])
        connection.close()
        return bodies

    recorded, replayed, _ = record_and_replay(cassette_path, upstream, action)
    assert recorded == replayed == [f"/echo?i={i}" for i in range(5)]


def test_exit_does_not_wait_for_idle_client_connections(cassette_path, upstream):
    with vcr.use_cassette(cassette_path, base_url=upstream.url) as cass:
        connection = connect(cass)
        connection.request("GET", "/echo")
        connection.getresponse().read()
        started = time.monotonic()
    assert time.monotonic() - started < 2
    connection.close()


def test_connection_close_is_honoured(cassette_path, upstream):
    with vcr.use_cassette(cassette_path, base_url=upstream.url) as cass:
        _, headers, _ = fetch(cass, "GET", "/echo", headers={"Connection": "close"})
    assert headers["Connection"] == "close"
    assert "Connection" not in cass.requests[0].headers


def test_concurrent_requests(cassette_path, upstream):
    paths = [f"/slow?i={i}" for i in range(20)]

    def action(cass):
        results = {}

        def worker(path):
            results[path] = fetch(cass, "GET", path)[2]

        threads = [threading.Thread(target=worker, args=(path,)) for path in paths]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        return results

    started = time.monotonic()
    recorded, replayed, _ = record_and_replay(cassette_path, upstream, action)
    # Forwarding is not serialized: 20 requests of 0.2s each finish well under 4s.
    assert time.monotonic() - started < 4
    assert recorded == replayed == {path: path.encode() for path in paths}


def test_https_upstream_without_verification(cassette_path, httpbin_secure):
    def action(cass):
        with urlopen(cass.url + "/get?q=1") as response:
            return json.loads(response.read())["args"]

    for record_mode in ("once", "none"):
        with vcr.use_cassette(
            cassette_path,
            base_url=httpbin_secure.url,
            verify_upstream_ssl=False,
            record_mode=record_mode,
        ) as cass:
            assert action(cass) == {"q": "1"}
    assert cass.requests[0].uri == httpbin_secure.url + "/get?q=1"


def test_https_upstream_with_custom_ssl_context(cassette_path, httpbin_secure):
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with vcr.use_cassette(cassette_path, base_url=httpbin_secure.url, verify_upstream_ssl=context) as cass:
        assert fetch(cass, "GET", "/get")[0] == 200


def test_https_upstream_verification_failure_is_reported(cassette_path, httpbin_secure):
    with (
        pytest.raises(ssl.SSLCertVerificationError),
        vcr.use_cassette(cassette_path, base_url=httpbin_secure.url) as cass,
    ):
        assert fetch(cass, "GET", "/get")[0] == ERROR_STATUS


def test_errors_on_one_request_do_not_break_the_next(cassette_path, upstream):
    with vcr.use_cassette(cassette_path, base_url=upstream.url) as cass:
        fetch(cass, "GET", "/echo")
    with (
        pytest.raises(CannotOverwriteExistingCassetteException),
        vcr.use_cassette(cassette_path, base_url=upstream.url) as cass,
    ):
        connection = connect(cass)
        connection.request("GET", "/unknown")
        assert connection.getresponse().read()
        connection.request("GET", "/echo")
        assert connection.getresponse().status == 200
        connection.close()
