import queue
import re
import socket
from contextlib import contextmanager
from urllib.request import urlopen

import pytest
import pytest_httpbin

import vcr
from vcr.stubs import VCRHTTPResponse


@contextmanager
def overridden_dns(overrides):
    """
    Monkeypatch socket.getaddrinfo() to override DNS lookups (name will resolve
    to address)
    """
    real_getaddrinfo = socket.getaddrinfo

    def fake_getaddrinfo(*args, **kwargs):
        if args[0] in overrides:
            address = overrides[args[0]]
            return [(2, 1, 6, "", (address, args[1]))]
        return real_getaddrinfo(*args, **kwargs)

    socket.getaddrinfo = fake_getaddrinfo
    yield
    socket.getaddrinfo = real_getaddrinfo


def test_ignore_localhost(tmpdir, httpbin):
    with overridden_dns({"httpbin.org": "127.0.0.1"}):
        cass_file = str(tmpdir.join("filter_qs.yaml"))
        with vcr.use_cassette(cass_file, ignore_localhost=True) as cass:
            urlopen(f"http://localhost:{httpbin.port}/")
            assert len(cass) == 0
            urlopen(f"http://httpbin.org:{httpbin.port}/")
            assert len(cass) == 1


def test_ignore_httpbin(tmpdir, httpbin):
    with overridden_dns({"httpbin.org": "127.0.0.1"}):
        cass_file = str(tmpdir.join("filter_qs.yaml"))
        with vcr.use_cassette(cass_file, ignore_hosts=["httpbin.org"]) as cass:
            urlopen(f"http://httpbin.org:{httpbin.port}/")
            assert len(cass) == 0
            urlopen(f"http://localhost:{httpbin.port}/")
            assert len(cass) == 1


def test_ignore_httpbin_regex(tmpdir, httpbin):
    with overridden_dns({"httpbin.org": "127.0.0.1"}):
        cass_file = str(tmpdir.join("filter_qs.yaml"))
        with vcr.use_cassette(cass_file, ignore_hosts=[re.compile(r"h\w*bin\.org")]) as cass:
            urlopen(f"http://httpbin.org:{httpbin.port}/")
            assert len(cass) == 0
            urlopen(f"http://localhost:{httpbin.port}/")
            assert len(cass) == 1


def test_ignore_localhost_and_httpbin(tmpdir, httpbin):
    with overridden_dns({"httpbin.org": "127.0.0.1"}):
        cass_file = str(tmpdir.join("filter_qs.yaml"))
        with vcr.use_cassette(cass_file, ignore_hosts=["httpbin.org"], ignore_localhost=True) as cass:
            urlopen(f"http://httpbin.org:{httpbin.port}")
            urlopen(f"http://localhost:{httpbin.port}")
            assert len(cass) == 0


def test_ignore_localhost_twice(tmpdir, httpbin):
    with overridden_dns({"httpbin.org": "127.0.0.1"}):
        cass_file = str(tmpdir.join("filter_qs.yaml"))
        with vcr.use_cassette(cass_file, ignore_localhost=True) as cass:
            urlopen(f"http://localhost:{httpbin.port}")
            assert len(cass) == 0
            urlopen(f"http://httpbin.org:{httpbin.port}")
            assert len(cass) == 1
        with vcr.use_cassette(cass_file, ignore_localhost=True) as cass:
            assert len(cass) == 1
            urlopen(f"http://localhost:{httpbin.port}")
            urlopen(f"http://httpbin.org:{httpbin.port}")
            assert len(cass) == 1


@pytest.mark.parametrize("record_mode", ["all", "none", "once", "new_episodes"])
@pytest.mark.parametrize("ignore", ["localhost", "hosts", "callback"])
def test_ignored_cachecontrol_response(tmpdir, httpbin_both, record_mode, ignore):
    requests = pytest.importorskip("requests")
    cachecontrol = pytest.importorskip("cachecontrol")
    options = {
        "localhost": {"ignore_localhost": True},
        "hosts": {"ignore_hosts": [httpbin_both.host]},
        "callback": {"before_record_request": lambda request: None},
    }[ignore]
    with cachecontrol.CacheControl(requests.Session()) as session:
        session.trust_env = False
        with vcr.use_cassette(
            str(tmpdir.join("ignored_cachecontrol.yaml")),
            record_mode=record_mode,
            **options,
        ) as cassette:
            for _ in range(2):
                with session.get(
                    httpbin_both.url + "/cache/60",
                    verify=pytest_httpbin.certs.where(),
                    timeout=2,
                ) as response:
                    assert response.status_code == 200
                    assert not isinstance(response.raw, VCRHTTPResponse)
                    assert response.json()["url"].endswith("/cache/60")
            assert response.from_cache is True
            assert len(cassette) == 0


@pytest.mark.parametrize("record_mode", ["all", "none"])
@pytest.mark.parametrize("finish", ["read", "stream", "release_conn"])
def test_ignored_response_finished_after_cassette(tmpdir, httpbin, record_mode, finish):
    urllib3 = pytest.importorskip("urllib3")
    with urllib3.PoolManager(maxsize=1, block=True) as manager:
        pool = manager.connection_from_url(httpbin.url)
        if not isinstance(pool.pool, queue.LifoQueue):
            pytest.skip("checks urllib3's pool of idle connections")
        with vcr.use_cassette(
            str(tmpdir.join("ignored_stream.yaml")),
            record_mode=record_mode,
            ignore_localhost=True,
        ) as cassette:
            response = manager.request(
                "GET",
                httpbin.url + "/get",
                preload_content=False,
                timeout=2,
                retries=False,
            )
            assert not isinstance(response, VCRHTTPResponse)
            assert response.tell() == 0
            assert len(cassette) == 0
        if finish == "read":
            response.read()
        elif finish == "stream":
            b"".join(response.stream())
        else:
            response.release_conn()
        assert pool.pool.qsize() == 1
        assert all(connection is None for connection in pool.pool.queue)
        outside = manager.request(
            "GET",
            httpbin.url + "/get",
            pool_timeout=0.1,
            timeout=2,
            retries=False,
        )
        assert outside.status == 200
        assert not isinstance(outside, VCRHTTPResponse)


def test_ignored_streams_across_nested_and_repeated_cassettes(tmpdir, httpbin):
    urllib3 = pytest.importorskip("urllib3")
    with urllib3.PoolManager(maxsize=2, block=True) as manager:
        pool = manager.connection_from_url(httpbin.url)
        if not isinstance(pool.pool, queue.LifoQueue):
            pytest.skip("checks urllib3's pool of idle connections")
        guard = None
        for number in range(2):
            with vcr.use_cassette(
                str(tmpdir.join(f"outer{number}.yaml")),
                ignore_localhost=True,
            ):
                outer = manager.request("GET", httpbin.url + "/get", preload_content=False)
                with vcr.use_cassette(
                    str(tmpdir.join(f"inner{number}.yaml")),
                    ignore_localhost=True,
                ):
                    inner = manager.request("GET", httpbin.url + "/get", preload_content=False)
                inner.release_conn()
                assert pool.pool.qsize() == 1
                assert pool.pool.queue[0] is None
            outer.release_conn()
            assert pool.pool.qsize() == 2
            assert all(connection is None for connection in pool.pool.queue)
            if guard is not None:
                assert pool._put_conn is guard
            guard = pool._put_conn
        assert (
            manager.request(
                "GET",
                httpbin.url + "/get",
                pool_timeout=0.1,
                timeout=2,
                retries=False,
            ).status
            == 200
        )
