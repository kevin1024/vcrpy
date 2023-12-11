import base64
import json
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

import vcr

from ..assertions import assert_cassette_has_one_response, assert_is_json_bytes


def _request_with_auth(url, username, password):
    request = Request(url)
    base64string = base64.b64encode(username.encode("ascii") + b":" + password.encode("ascii"))
    request.add_header(b"Authorization", b"Basic " + base64string)
    return urlopen(request)


def _find_header(cassette, header):
    return any(header in request.headers for request in cassette.requests)


def test_filter_basic_auth(tmpdir, httpbin):
    url = httpbin.url + "/basic-auth/user/passwd"
    cass_file = str(tmpdir.join("basic_auth_filter.yaml"))
    my_vcr = vcr.VCR(match_on=["uri", "method", "headers"])
    # 2 requests, one with auth failure and one with auth success
    with my_vcr.use_cassette(cass_file, filter_headers=["authorization"]):
        with pytest.raises(HTTPError):
            resp = _request_with_auth(url, "user", "wrongpasswd")
            assert resp.getcode() == 401
        resp = _request_with_auth(url, "user", "passwd")
        assert resp.getcode() == 200
    # make same 2 requests, this time both served from cassette.
    with my_vcr.use_cassette(cass_file, filter_headers=["authorization"]) as cass:
        with pytest.raises(HTTPError):
            resp = _request_with_auth(url, "user", "wrongpasswd")
            assert resp.getcode() == 401
        resp = _request_with_auth(url, "user", "passwd")
        assert resp.getcode() == 200
        # authorization header should not have been recorded
        assert not _find_header(cass, "authorization")
        assert len(cass) == 2


def test_filter_querystring(tmpdir, httpbin):
    url = httpbin.url + "/?password=secret"
    cass_file = str(tmpdir.join("filter_qs.yaml"))
    with vcr.use_cassette(cass_file, filter_query_parameters=["password"]):
        urlopen(url)
    with vcr.use_cassette(cass_file, filter_query_parameters=["password"]) as cass:
        urlopen(url)
        assert "password" not in cass.requests[0].url
        assert "secret" not in cass.requests[0].url
    with open(cass_file) as f:
        cassette_content = f.read()
        assert "password" not in cassette_content
        assert "secret" not in cassette_content


def test_filter_post_data(tmpdir, httpbin):
    url = httpbin.url + "/post"
    data = urlencode({"id": "secret", "foo": "bar"}).encode("utf-8")
    cass_file = str(tmpdir.join("filter_pd.yaml"))
    with vcr.use_cassette(cass_file, filter_post_data_parameters=["id"]):
        urlopen(url, data)
    with vcr.use_cassette(cass_file, filter_post_data_parameters=["id"]) as cass:
        assert b"id=secret" not in cass.requests[0].body


def test_filter_json_post_data(tmpdir, httpbin):
    data = json.dumps({"id": "secret", "foo": "bar"}).encode("utf-8")
    request = Request(httpbin.url + "/post", data=data)
    request.add_header("Content-Type", "application/json")

    cass_file = str(tmpdir.join("filter_jpd.yaml"))
    with vcr.use_cassette(cass_file, filter_post_data_parameters=["id"]):
        urlopen(request)
    with vcr.use_cassette(cass_file, filter_post_data_parameters=["id"]) as cass:
        assert b'"id": "secret"' not in cass.requests[0].body


def test_filter_callback(tmpdir, httpbin):
    url = httpbin.url + "/get"
    cass_file = str(tmpdir.join("basic_auth_filter.yaml"))

    def before_record_cb(request):
        if request.path != "/get":
            return request

    # Test the legacy keyword.
    my_vcr = vcr.VCR(before_record=before_record_cb)
    with my_vcr.use_cassette(cass_file, filter_headers=["authorization"]) as cass:
        urlopen(url)
        assert len(cass) == 0

    my_vcr = vcr.VCR(before_record_request=before_record_cb)
    with my_vcr.use_cassette(cass_file, filter_headers=["authorization"]) as cass:
        urlopen(url)
        assert len(cass) == 0


def test_decompress_gzip(tmpdir, httpbin):
    url = httpbin.url + "/gzip"
    request = Request(url, headers={"Accept-Encoding": ["gzip, deflate"]})
    cass_file = str(tmpdir.join("gzip_response.yaml"))
    with vcr.use_cassette(cass_file, decode_compressed_response=True):
        urlopen(request)
    with vcr.use_cassette(cass_file) as cass:
        decoded_response = urlopen(url).read()
        assert_cassette_has_one_response(cass)
    assert_is_json_bytes(decoded_response)


def test_decomptess_empty_body(tmpdir, httpbin):
    url = httpbin.url + "/gzip"
    request = Request(url, headers={"Accept-Encoding": ["gzip, deflate"]}, method="HEAD")
    cass_file = str(tmpdir.join("gzip_empty_response.yaml"))
    with vcr.use_cassette(cass_file, decode_compressed_response=True):
        response = urlopen(request).read()
    with vcr.use_cassette(cass_file) as cass:
        decoded_response = urlopen(request).read()
        assert_cassette_has_one_response(cass)
    assert decoded_response == response


def test_decompress_deflate(tmpdir, httpbin):
    url = httpbin.url + "/deflate"
    request = Request(url, headers={"Accept-Encoding": ["gzip, deflate"]})
    cass_file = str(tmpdir.join("deflate_response.yaml"))
    with vcr.use_cassette(cass_file, decode_compressed_response=True):
        urlopen(request)
    with vcr.use_cassette(cass_file) as cass:
        decoded_response = urlopen(url).read()
        assert_cassette_has_one_response(cass)
    assert_is_json_bytes(decoded_response)


def test_decompress_regular(tmpdir, httpbin):
    """Test that it doesn't try to decompress content that isn't compressed"""
    url = httpbin.url + "/get"
    cass_file = str(tmpdir.join("noncompressed_response.yaml"))
    with vcr.use_cassette(cass_file, decode_compressed_response=True):
        urlopen(url)
    with vcr.use_cassette(cass_file) as cass:
        resp = urlopen(url).read()
        assert_cassette_has_one_response(cass)
    assert_is_json_bytes(resp)


def test_before_record_request_corruption(tmpdir, httpbin):
    """Modifying request in before_record_request should not affect outgoing request"""

    def before_record(request):
        request.headers.clear()
        request.body = b""
        return request

    req = Request(
        httpbin.url + "/post",
        data=urlencode({"test": "exists"}).encode(),
        headers={"X-Test": "exists"},
    )
    cass_file = str(tmpdir.join("modified_response.yaml"))
    with vcr.use_cassette(cass_file, before_record_request=before_record):
        resp = json.loads(urlopen(req).read())

    assert resp["headers"]["X-Test"] == "exists"
    assert resp["form"]["test"] == "exists"
