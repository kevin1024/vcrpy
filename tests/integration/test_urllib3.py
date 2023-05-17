"""Integration tests with urllib3"""

# coding=utf-8

import pytest
from assertions import assert_cassette_empty, assert_is_json

import vcr
from vcr.patch import force_reset
from vcr.stubs.compat import get_headers

urllib3 = pytest.importorskip("urllib3")


def test_status_code(httpbin_both, tmpdir):
    """Ensure that we can read the status code"""
    url = httpbin_both.url
    with vcr.use_cassette(str(tmpdir.join("atts.yaml"))):
        status_code = urllib3.request("GET", url).status

    with vcr.use_cassette(str(tmpdir.join("atts.yaml"))):
        assert status_code == urllib3.request("GET", url).status


def test_headers(tmpdir, httpbin_both):
    """Ensure that we can read the headers back"""
    url = httpbin_both.url
    with vcr.use_cassette(str(tmpdir.join("headers.yaml"))):
        headers = urllib3.request("GET", url).headers

    with vcr.use_cassette(str(tmpdir.join("headers.yaml"))):
        new_headers = urllib3.request("GET", url).headers
        assert sorted(get_headers(headers)) == sorted(get_headers(new_headers))


def test_body(tmpdir, httpbin_both):
    """Ensure the responses are all identical enough"""
    url = httpbin_both.url + "/bytes/1024"
    with vcr.use_cassette(str(tmpdir.join("body.yaml"))):
        content = urllib3.request("GET", url).data

    with vcr.use_cassette(str(tmpdir.join("body.yaml"))):
        assert content == urllib3.request("GET", url).data


def test_auth(tmpdir, httpbin_both):
    """Ensure that we can handle basic auth"""
    auth = ("user", "passwd")
    headers = urllib3.util.make_headers(basic_auth="{}:{}".format(*auth))
    url = httpbin_both.url + "/basic-auth/user/passwd"
    with vcr.use_cassette(str(tmpdir.join("auth.yaml"))):
        one = urllib3.request("GET", url, headers=headers)

    with vcr.use_cassette(str(tmpdir.join("auth.yaml"))):
        two = urllib3.request("GET", url, headers=headers)
        assert one.data == two.data
        assert one.status == two.status


def test_auth_failed(tmpdir, httpbin_both):
    """Ensure that we can save failed auth statuses"""
    auth = ("user", "wrongwrongwrong")
    headers = urllib3.util.make_headers(basic_auth="{}:{}".format(*auth))
    url = httpbin_both.url + "/basic-auth/user/passwd"
    with vcr.use_cassette(str(tmpdir.join("auth-failed.yaml"))) as cass:
        # Ensure that this is empty to begin with
        assert_cassette_empty(cass)
        one = urllib3.request("GET", url, headers=headers)
        two = urllib3.request("GET", url, headers=headers)
        assert one.data == two.data
        assert one.status == two.status == 401


def test_post(tmpdir, httpbin_both):
    """Ensure that we can post and cache the results"""
    data = {"key1": "value1", "key2": "value2"}
    url = httpbin_both.url + "/post"
    with vcr.use_cassette(str(tmpdir.join("verify_pool_mgr.yaml"))):
        req1 = urllib3.request("POST", url, data).data

    with vcr.use_cassette(str(tmpdir.join("verify_pool_mgr.yaml"))):
        req2 = urllib3.request("POST", url, data).data

    assert req1 == req2


def test_redirects(tmpdir):
    """Ensure that we can handle redirects"""
    url = "http://mockbin.org/redirect/301"

    with vcr.use_cassette(str(tmpdir.join("verify_pool_mgr.yaml"))):
        content = urllib3.request("GET", url).data

    with vcr.use_cassette(str(tmpdir.join("verify_pool_mgr.yaml"))) as cass:
        assert content == urllib3.request("GET", url).data
        # Ensure that we've now cached *two* responses. One for the redirect
        # and one for the final fetch

    assert len(cass) == 2
    assert cass.play_count == 2


def test_cross_scheme(tmpdir, httpbin, httpbin_secure):
    """Ensure that requests between schemes are treated separately"""
    # First fetch a url under http, and then again under https and then
    # ensure that we haven't served anything out of cache, and we have two
    # requests / response pairs in the cassette
    with vcr.use_cassette(str(tmpdir.join("cross_scheme.yaml"))) as cass:
        urllib3.request("GET", httpbin_secure.url)
        urllib3.request("GET", httpbin.url)
        assert cass.play_count == 0
        assert len(cass) == 2


def test_gzip(tmpdir, httpbin_both):
    """
    Ensure that requests (actually urllib3) is able to automatically decompress
    the response body
    """
    url = httpbin_both.url + "/gzip"
    response = urllib3.request("GET", url)

    with vcr.use_cassette(str(tmpdir.join("gzip.yaml"))):
        response = urllib3.request("GET", url)
        assert_is_json(response.data)

    with vcr.use_cassette(str(tmpdir.join("gzip.yaml"))):
        assert_is_json(response.data)


def test_https_with_cert_validation_disabled(tmpdir, httpbin_secure):
    with vcr.use_cassette(str(tmpdir.join("cert_validation_disabled.yaml"))):
        urllib3.request("GET", httpbin_secure.url)


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
