import http.client
import io
import re
import socket
from contextlib import contextmanager
from urllib.request import urlopen

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


def test_ignored_host_returns_real_response(tmpdir, httpbin):
    """An ignored host's response must be the real http.client response.

    The VCRHTTPResponse wrapper sets ``fp`` but not ``_fp``, which breaks
    consumers that rely on real response internals (e.g. CacheControl)
    even though the request was never going to be recorded.
    """
    cass_file = str(tmpdir.join("ignore_real_response.yaml"))
    with vcr.use_cassette(cass_file, ignore_localhost=True) as cass:
        conn = http.client.HTTPConnection("localhost", httpbin.port)
        conn.request("GET", "/")
        response = conn.getresponse()
        assert not isinstance(response, VCRHTTPResponse)
        assert type(response) is http.client.HTTPResponse
        # The body has not been pre-read into a BytesIO by VCR: the
        # caller reads it from the real response stream.
        assert not isinstance(response.fp, io.BytesIO)
        assert response.status == 200
        assert response.read()
        conn.close()
        assert len(cass) == 0
