"""Integration tests with urllib3"""

# coding=utf-8

import json
import queue
from collections.abc import Mapping
from contextlib import nullcontext

import pytest
import pytest_httpbin

import vcr
from vcr.patch import force_reset
from vcr.stubs import VCRHTTPResponse
from vcr.stubs.urllib3_stubs import VCRRequestsHTTPSConnection

from ..assertions import assert_cassette_empty, assert_is_json_bytes

urllib3 = pytest.importorskip("urllib3")


@pytest.fixture(scope="module")
def verify_pool_mgr():
    return urllib3.PoolManager(
        cert_reqs="CERT_REQUIRED",
        ca_certs=pytest_httpbin.certs.where(),  # Force certificate check.
    )


@pytest.fixture(scope="module")
def pool_mgr():
    return urllib3.PoolManager(cert_reqs="CERT_NONE")


def test_status_code(httpbin_both, tmpdir, verify_pool_mgr):
    """Ensure that we can read the status code"""
    url = httpbin_both.url
    with vcr.use_cassette(str(tmpdir.join("atts.yaml"))):
        status_code = verify_pool_mgr.request("GET", url).status

    with vcr.use_cassette(str(tmpdir.join("atts.yaml"))):
        assert status_code == verify_pool_mgr.request("GET", url).status


def test_url(httpbin_both, tmpdir, verify_pool_mgr):
    """Ensure that we can read the URL"""
    url = httpbin_both.url
    with vcr.use_cassette(str(tmpdir.join("url.yaml"))):
        url = verify_pool_mgr.request("GET", url).geturl()

    with vcr.use_cassette(str(tmpdir.join("url.yaml"))):
        assert url == verify_pool_mgr.request("GET", url).geturl()


def test_headers(tmpdir, httpbin_both, verify_pool_mgr):
    """Ensure that we can read the headers back"""
    url = httpbin_both.url
    with vcr.use_cassette(str(tmpdir.join("headers.yaml"))):
        headers = verify_pool_mgr.request("GET", url).headers
        assert isinstance(headers, Mapping)

    with vcr.use_cassette(str(tmpdir.join("headers.yaml"))):
        new_headers = verify_pool_mgr.request("GET", url).headers
        assert isinstance(new_headers, Mapping)
        assert sorted(headers.items()) == sorted(new_headers.items())


def test_body(tmpdir, httpbin_both, verify_pool_mgr):
    """Ensure the responses are all identical enough"""
    url = httpbin_both.url + "/bytes/1024"
    with vcr.use_cassette(str(tmpdir.join("body.yaml"))):
        content = verify_pool_mgr.request("GET", url).data

    with vcr.use_cassette(str(tmpdir.join("body.yaml"))):
        assert content == verify_pool_mgr.request("GET", url).data


def test_auth(tmpdir, httpbin_both, verify_pool_mgr):
    """Ensure that we can handle basic auth"""
    auth = ("user", "passwd")
    headers = urllib3.util.make_headers(basic_auth="{}:{}".format(*auth))
    url = httpbin_both.url + "/basic-auth/user/passwd"
    with vcr.use_cassette(str(tmpdir.join("auth.yaml"))):
        one = verify_pool_mgr.request("GET", url, headers=headers)

    with vcr.use_cassette(str(tmpdir.join("auth.yaml"))):
        two = verify_pool_mgr.request("GET", url, headers=headers)
        assert one.data == two.data
        assert one.status == two.status


def test_auth_failed(tmpdir, httpbin_both, verify_pool_mgr):
    """Ensure that we can save failed auth statuses"""
    auth = ("user", "wrongwrongwrong")
    headers = urllib3.util.make_headers(basic_auth="{}:{}".format(*auth))
    url = httpbin_both.url + "/basic-auth/user/passwd"
    with vcr.use_cassette(str(tmpdir.join("auth-failed.yaml"))) as cass:
        # Ensure that this is empty to begin with
        assert_cassette_empty(cass)
        one = verify_pool_mgr.request("GET", url, headers=headers)
        two = verify_pool_mgr.request("GET", url, headers=headers)
        assert one.data == two.data
        assert one.status == two.status == 401


def test_post(tmpdir, httpbin_both, verify_pool_mgr):
    """Ensure that we can post and cache the results"""
    data = {"key1": "value1", "key2": "value2"}
    url = httpbin_both.url + "/post"
    with vcr.use_cassette(str(tmpdir.join("verify_pool_mgr.yaml"))):
        req1 = verify_pool_mgr.request("POST", url, fields=data).data

    with vcr.use_cassette(str(tmpdir.join("verify_pool_mgr.yaml"))):
        req2 = verify_pool_mgr.request("POST", url, fields=data).data

    assert json.loads(req1)["form"] == data
    assert req1 == req2


@pytest.mark.online
def test_redirects(tmpdir, verify_pool_mgr, httpbin):
    """Ensure that we can handle redirects"""
    url = httpbin.url + "/redirect/1"

    with vcr.use_cassette(str(tmpdir.join("verify_pool_mgr.yaml"))):
        content = verify_pool_mgr.request("GET", url).data

    with vcr.use_cassette(str(tmpdir.join("verify_pool_mgr.yaml"))) as cass:
        assert content == verify_pool_mgr.request("GET", url).data
        # Ensure that we've now cached *two* responses. One for the redirect
        # and one for the final fetch

    assert len(cass) == 2
    assert cass.play_count == 2


def test_cross_scheme(tmpdir, httpbin, httpbin_secure, verify_pool_mgr):
    """Ensure that requests between schemes are treated separately"""
    # First fetch a url under http, and then again under https and then
    # ensure that we haven't served anything out of cache, and we have two
    # requests / response pairs in the cassette
    with vcr.use_cassette(str(tmpdir.join("cross_scheme.yaml"))) as cass:
        verify_pool_mgr.request("GET", httpbin_secure.url)
        verify_pool_mgr.request("GET", httpbin.url)
        assert cass.play_count == 0
        assert len(cass) == 2


def test_gzip(tmpdir, httpbin_both, verify_pool_mgr):
    """
    Ensure that requests (actually urllib3) is able to automatically decompress
    the response body
    """
    url = httpbin_both.url + "/gzip"
    response = verify_pool_mgr.request("GET", url)

    with vcr.use_cassette(str(tmpdir.join("gzip.yaml"))):
        response = verify_pool_mgr.request("GET", url)
        assert_is_json_bytes(response.data)

    with vcr.use_cassette(str(tmpdir.join("gzip.yaml"))):
        assert_is_json_bytes(response.data)


def test_https_with_cert_validation_disabled(tmpdir, httpbin_secure, pool_mgr):
    with vcr.use_cassette(str(tmpdir.join("cert_validation_disabled.yaml"))):
        pool_mgr.request("GET", httpbin_secure.url)


def test_urllib3_force_reset():
    conn = urllib3.connection
    http_original = conn.HTTPConnection
    https_original = conn.HTTPSConnection
    verified_https_original = conn.VerifiedHTTPSConnection
    with vcr.use_cassette(path="test"):
        first_cassette_HTTPConnection = conn.HTTPConnection
        first_cassette_HTTPSConnection = conn.HTTPSConnection
        first_cassette_VerifiedHTTPSConnection = conn.VerifiedHTTPSConnection
        with force_reset():
            assert conn.HTTPConnection is http_original
            assert conn.HTTPSConnection is https_original
            assert conn.VerifiedHTTPSConnection is verified_https_original
        assert conn.HTTPConnection is first_cassette_HTTPConnection
        assert conn.HTTPSConnection is first_cassette_HTTPSConnection
        assert conn.VerifiedHTTPSConnection is first_cassette_VerifiedHTTPSConnection


def test_repeated_headers(tmpdir, httpbin_both, verify_pool_mgr):
    # A header sent more than once keeps every value (#947).
    url = httpbin_both.url + "/response-headers?Link=a&Link=b"
    with vcr.use_cassette(str(tmpdir.join("repeated_headers.yaml"))):
        assert verify_pool_mgr.request("GET", url).headers.getlist("Link") == ["a", "b"]

    with vcr.use_cassette(str(tmpdir.join("repeated_headers.yaml"))) as cassette:
        assert verify_pool_mgr.request("GET", url).headers.getlist("Link") == ["a", "b"]
        assert cassette.play_count == 1


@pytest.mark.parametrize("record_mode", ["all", "none"])
@pytest.mark.parametrize("preload_content", [False, True])
def test_release_conn_restores_pool_capacity(tmpdir, httpbin, record_mode, preload_content):
    path = str(tmpdir.join("release_conn.yaml"))
    urls = [f"{httpbin.url}/get?request={number}" for number in range(2)]
    with vcr.use_cassette(path), urllib3.PoolManager() as manager:
        for url in urls:
            assert manager.request("GET", url).status == 200

    with (
        vcr.use_cassette(path, record_mode=record_mode) as cassette,
        urllib3.PoolManager(maxsize=1, block=True) as manager,
    ):
        pool = manager.connection_from_url(httpbin.url)
        if not isinstance(pool.pool, queue.LifoQueue):
            # urllib3-future (installed with niquests) keeps leased connections in its pool.
            pytest.skip("checks urllib3's pool of idle connections")
        previous = None
        for number, url in enumerate(urls):
            response = manager.request(
                "GET",
                url,
                preload_content=preload_content,
                pool_timeout=0.1,
                timeout=2,
                retries=False,
            )
            if previous is not None:
                previous.close()
            assert response.status == 200
            assert pool.pool.qsize() == int(preload_content)
            assert response.release_conn() is None
            assert pool.pool.qsize() == 1
            assert json.loads(response.read())["args"] == {"request": str(number)}
            previous = response
            assert response._connection is None
            assert response.release_conn() is None
            assert pool.pool.qsize() == 1

        assert cassette.play_count == (2 if record_mode == "none" else 0)


@pytest.mark.parametrize("record_mode", ["all", "none"])
@pytest.mark.parametrize("read", ["read", "stream"])
def test_reading_the_body_returns_the_connection(tmpdir, httpbin, record_mode, read):
    # requests reads a response with stream() and doesn't release it, so with a
    # blocking pool (e.g. pool_block=True) its next request waited forever (#949).
    path = str(tmpdir.join("read_body.yaml"))
    urls = [f"{httpbin.url}/get?request={number}" for number in range(2)]
    with vcr.use_cassette(path), urllib3.PoolManager() as manager:
        for url in urls:
            assert manager.request("GET", url).status == 200

    with (
        vcr.use_cassette(path, record_mode=record_mode) as cassette,
        urllib3.PoolManager(maxsize=1, block=True) as manager,
    ):
        if not isinstance(manager.connection_from_url(httpbin.url).pool, queue.LifoQueue):
            pytest.skip("checks urllib3's pool of idle connections")
        for number, url in enumerate(urls):
            response = manager.request(
                "GET",
                url,
                preload_content=False,
                pool_timeout=0.1,
                timeout=2,
                retries=False,
            )
            body = response.read() if read == "read" else b"".join(response.stream())
            assert json.loads(body)["args"] == {"request": str(number)}

        assert cassette.play_count == (2 if record_mode == "none" else 0)


@pytest.mark.parametrize("record_mode", ["all", "none"])
@pytest.mark.parametrize("finish", ["read", "stream", "release_conn"])
def test_finishing_a_response_after_its_cassette(tmpdir, httpbin, record_mode, finish):
    # The cassette's connection mustn't go back into the pool once the cassette has exited.
    path = str(tmpdir.join("finish_after.yaml"))
    url = f"{httpbin.url}/get"
    with vcr.use_cassette(path), urllib3.PoolManager() as manager:
        assert manager.request("GET", url).status == 200

    with urllib3.PoolManager(maxsize=1, block=True) as manager:
        if not isinstance(manager.connection_from_url(url).pool, queue.LifoQueue):
            pytest.skip("checks urllib3's pool of idle connections")
        with vcr.use_cassette(path, record_mode=record_mode):
            response = manager.request("GET", url, preload_content=False, timeout=2, retries=False)
        if finish == "read":
            response.read()
        elif finish == "stream":
            b"".join(response.stream())
        else:
            response.release_conn()

        response = manager.request("GET", url, pool_timeout=0.1, timeout=2, retries=False)
        assert response.status == 200
        assert not isinstance(response, VCRHTTPResponse)


@pytest.mark.parametrize("record_mode", ["all", "none"])
@pytest.mark.parametrize("uses", ["cassette, live", "live, cassette", "cassette, cassette"])
def test_blocking_pool_used_around_cassettes(tmpdir, httpbin, record_mode, uses):
    # vcrpy takes connections out of a pool when a cassette starts and stops
    # using it. Without their slots, a blocking pool waited forever (#949).
    path = str(tmpdir.join("around.yaml"))
    url = f"{httpbin.url}/get"
    with vcr.use_cassette(path), urllib3.PoolManager() as manager:
        assert manager.request("GET", url).status == 200

    with urllib3.PoolManager(maxsize=1, block=True) as manager:
        if not isinstance(manager.connection_from_url(url).pool, queue.LifoQueue):
            pytest.skip("checks urllib3's pool of idle connections")
        for use in uses.split(", "):
            in_cassette = use == "cassette"
            with vcr.use_cassette(path, record_mode=record_mode) if in_cassette else nullcontext():
                response = manager.request("GET", url, pool_timeout=0.1, timeout=2, retries=False)
            assert response.status == 200
            assert isinstance(response, VCRHTTPResponse) is in_cassette


@pytest.mark.parametrize("record_mode", ["once", "new_episodes", "all"])
def test_https_connects_only_to_send(tmpdir, httpbin_secure, record_mode, monkeypatch):
    # urllib3 connects before sending an HTTPS request, but a request that's
    # played back shouldn't open a connection, whatever the record mode (#515).
    path = str(tmpdir.join("connect.yaml"))
    url = httpbin_secure.url + "/get"
    with vcr.use_cassette(path):
        urllib3.PoolManager(cert_reqs="CERT_NONE").request("GET", url)

    # The class of the real connections vcrpy makes for urllib3
    real_connection_class = VCRRequestsHTTPSConnection._baseclass
    connect = real_connection_class.connect
    connections = []

    def counting_connect(self, *args, **kwargs):
        connections.append(self.host)
        return connect(self, *args, **kwargs)

    monkeypatch.setattr(real_connection_class, "connect", counting_connect)
    with vcr.use_cassette(path, record_mode=record_mode) as cassette:
        assert urllib3.PoolManager(cert_reqs="CERT_NONE").request("GET", url).status == 200

    played = record_mode != "all"
    assert cassette.play_count == int(played)
    assert len(connections) == int(not played)
