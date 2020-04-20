# -*- coding: utf-8 -*-
"""Test requests' interaction with vcr"""
import functools
import platform
import pytest
import sys
import vcr
from assertions import assert_cassette_empty, assert_is_json

requests = pytest.importorskip("requests")
from requests.exceptions import ConnectionError  # noqa E402


@pytest.fixture(params=[True, False])
def use_direct_method(request):
    """Fixture that returns True and False indicating to use direct method or request(method)."""
    return request.param


def request_func(method, direct_method, lookup=requests):
    if direct_method:
        return getattr(lookup, method.lower())
    else:
        return functools.partial(lookup.request, method.upper())


def test_status_code(httpbin_both, tmpdir, use_direct_method):
    """Ensure that we can read the status code"""
    url = httpbin_both.url + "/"
    with vcr.use_cassette(str(tmpdir.join("atts.yaml"))):
        status_code = request_func("GET", direct_method=use_direct_method)(url).status_code

    with vcr.use_cassette(str(tmpdir.join("atts.yaml"))):
        assert status_code == request_func("GET", direct_method=use_direct_method)(url).status_code


def test_headers(httpbin_both, tmpdir, use_direct_method):
    """Ensure that we can read the headers back"""
    url = httpbin_both + "/"
    with vcr.use_cassette(str(tmpdir.join("headers.yaml"))):
        headers = request_func("GET", direct_method=use_direct_method)(url).headers

    with vcr.use_cassette(str(tmpdir.join("headers.yaml"))):
        assert headers == request_func("GET", direct_method=use_direct_method)(url).headers


def test_body(tmpdir, httpbin_both, use_direct_method):
    """Ensure the responses are all identical enough"""
    url = httpbin_both + "/bytes/1024"
    with vcr.use_cassette(str(tmpdir.join("body.yaml"))):
        content = request_func("GET", direct_method=use_direct_method)(url).content

    with vcr.use_cassette(str(tmpdir.join("body.yaml"))):
        assert content == request_func("GET", direct_method=use_direct_method)(url).content


def test_get_empty_content_type_json(tmpdir, httpbin_both, use_direct_method):
    """Ensure GET with application/json content-type and empty request body doesn't crash"""
    url = httpbin_both + "/status/200"
    headers = {"Content-Type": "application/json"}

    with vcr.use_cassette(str(tmpdir.join("get_empty_json.yaml")), match_on=("body",)):
        status = request_func("GET", direct_method=use_direct_method)(url, headers=headers).status_code

    with vcr.use_cassette(str(tmpdir.join("get_empty_json.yaml")), match_on=("body",)):
        assert (
            status == request_func("GET", direct_method=use_direct_method)(url, headers=headers).status_code
        )


def test_effective_url(tmpdir, httpbin_both, use_direct_method):
    """Ensure that the effective_url is captured"""
    url = httpbin_both.url + "/redirect-to?url=/html"
    with vcr.use_cassette(str(tmpdir.join("url.yaml"))):
        effective_url = request_func("GET", direct_method=use_direct_method)(url).url
        assert effective_url == httpbin_both.url + "/html"

    with vcr.use_cassette(str(tmpdir.join("url.yaml"))):
        assert effective_url == request_func("GET", direct_method=use_direct_method)(url).url


def test_auth(tmpdir, httpbin_both, use_direct_method):
    """Ensure that we can handle basic auth"""
    auth = ("user", "passwd")
    url = httpbin_both + "/basic-auth/user/passwd"
    with vcr.use_cassette(str(tmpdir.join("auth.yaml"))):
        one = request_func("GET", direct_method=use_direct_method)(url, auth=auth)

    with vcr.use_cassette(str(tmpdir.join("auth.yaml"))):
        two = request_func("GET", direct_method=use_direct_method)(url, auth=auth)
        assert one.content == two.content
        assert one.status_code == two.status_code


def test_auth_failed(tmpdir, httpbin_both, use_direct_method):
    """Ensure that we can save failed auth statuses"""
    auth = ("user", "wrongwrongwrong")
    url = httpbin_both + "/basic-auth/user/passwd"
    with vcr.use_cassette(str(tmpdir.join("auth-failed.yaml"))) as cass:
        # Ensure that this is empty to begin with
        assert_cassette_empty(cass)
        one = request_func("GET", direct_method=use_direct_method)(url, auth=auth)
        two = request_func("GET", direct_method=use_direct_method)(url, auth=auth)
        assert one.content == two.content
        assert one.status_code == two.status_code == 401


def test_post(tmpdir, httpbin_both, use_direct_method):
    """Ensure that we can post and cache the results"""
    data = {"key1": "value1", "key2": "value2"}
    url = httpbin_both + "/post"
    with vcr.use_cassette(str(tmpdir.join("requests.yaml"))):
        req1 = request_func("POST", direct_method=use_direct_method)(url, data=data).content

    with vcr.use_cassette(str(tmpdir.join("requests.yaml"))):
        req2 = request_func("POST", direct_method=use_direct_method)(url, data=data).content

    assert req1 == req2


def test_post_chunked_binary(tmpdir, httpbin, use_direct_method):
    """Ensure that we can send chunked binary without breaking while trying to concatenate bytes with str."""
    data1 = iter([b"data", b"to", b"send"])
    data2 = iter([b"data", b"to", b"send"])
    url = httpbin.url + "/post"
    with vcr.use_cassette(str(tmpdir.join("requests.yaml"))):
        req1 = request_func("POST", direct_method=use_direct_method)(url, data=data1).content

    with vcr.use_cassette(str(tmpdir.join("requests.yaml"))):
        req2 = request_func("POST", direct_method=use_direct_method)(url, data=data2).content

    assert req1 == req2


@pytest.mark.skipif("sys.version_info >= (3, 6)", strict=True, raises=ConnectionError)
@pytest.mark.skipif(
    (3, 5) < sys.version_info < (3, 6) and platform.python_implementation() == "CPython",
    reason="Fails on CPython 3.5",
)
def test_post_chunked_binary_secure(tmpdir, httpbin_secure, use_direct_method):
    """Ensure that we can send chunked binary without breaking while trying to concatenate bytes with str."""
    data1 = iter([b"data", b"to", b"send"])
    data2 = iter([b"data", b"to", b"send"])
    url = httpbin_secure.url + "/post"
    with vcr.use_cassette(str(tmpdir.join("requests.yaml"))):
        req1 = request_func("POST", direct_method=use_direct_method)(url, data=data1).content
        print(req1)

    with vcr.use_cassette(str(tmpdir.join("requests.yaml"))):
        req2 = request_func("POST", direct_method=use_direct_method)(url, data=data2).content

    assert req1 == req2


def test_redirects(tmpdir, httpbin_both, use_direct_method):
    """Ensure that we can handle redirects"""
    url = httpbin_both + "/redirect-to?url=bytes/1024"
    with vcr.use_cassette(str(tmpdir.join("requests.yaml"))):
        content = request_func("GET", direct_method=use_direct_method)(url).content

    with vcr.use_cassette(str(tmpdir.join("requests.yaml"))) as cass:
        assert content == request_func("GET", direct_method=use_direct_method)(url).content
        # Ensure that we've now cached *two* responses. One for the redirect
        # and one for the final fetch
        assert len(cass) == 2
        assert cass.play_count == 2


def test_cross_scheme(tmpdir, httpbin_secure, httpbin, use_direct_method):
    """Ensure that requests between schemes are treated separately"""
    # First fetch a url under http, and then again under https and then
    # ensure that we haven't served anything out of cache, and we have two
    # requests / response pairs in the cassette
    with vcr.use_cassette(str(tmpdir.join("cross_scheme.yaml"))) as cass:
        request_func("GET", direct_method=use_direct_method)(httpbin_secure + "/")
        request_func("GET", direct_method=use_direct_method)(httpbin + "/")
        assert cass.play_count == 0
        assert len(cass) == 2


def test_gzip(tmpdir, httpbin_both, use_direct_method):
    """
    Ensure that requests (actually urllib3) is able to automatically decompress
    the response body
    """
    url = httpbin_both + "/gzip"
    response = request_func("GET", direct_method=use_direct_method)(url)

    with vcr.use_cassette(str(tmpdir.join("gzip.yaml"))):
        response = request_func("GET", direct_method=use_direct_method)(url)
        assert_is_json(response.content)

    with vcr.use_cassette(str(tmpdir.join("gzip.yaml"))):
        assert_is_json(response.content)


def test_session_and_connection_close(tmpdir, httpbin, use_direct_method):
    """
    This tests the issue in https://github.com/kevin1024/vcrpy/issues/48

    If you use a requests.session and the connection is closed, then an
    exception is raised in the urllib3 module vendored into requests:
    `AttributeError: 'NoneType' object has no attribute 'settimeout'`
    """
    with vcr.use_cassette(str(tmpdir.join("session_connection_closed.yaml"))):
        session = requests.session()

        request_func("GET", direct_method=use_direct_method, lookup=session)(
            httpbin + "/get", headers={"Connection": "close"}
        )
        request_func("GET", direct_method=use_direct_method, lookup=session)(
            httpbin + "/get", headers={"Connection": "close"}
        )


def test_https_with_cert_validation_disabled(tmpdir, httpbin_secure, use_direct_method):
    with vcr.use_cassette(str(tmpdir.join("cert_validation_disabled.yaml"))):
        request_func("GET", direct_method=use_direct_method)(httpbin_secure.url, verify=False)


def test_session_can_make_requests_after_requests_unpatched(tmpdir, httpbin, use_direct_method):
    with vcr.use_cassette(str(tmpdir.join("test_session_after_unpatched.yaml"))):
        session = requests.session()
        request_func("GET", direct_method=use_direct_method, lookup=session)(httpbin + "/get")

    with vcr.use_cassette(str(tmpdir.join("test_session_after_unpatched.yaml"))):
        session = requests.session()
        request_func("GET", direct_method=use_direct_method, lookup=session)(httpbin + "/get")

    request_func("GET", direct_method=use_direct_method, lookup=session)(httpbin + "/status/200")


def test_session_created_before_use_cassette_is_patched(tmpdir, httpbin_both, use_direct_method):
    url = httpbin_both + "/bytes/1024"
    # Record arbitrary, random data to the cassette
    with vcr.use_cassette(str(tmpdir.join("session_created_outside.yaml"))):
        session = requests.session()
        body = request_func("GET", direct_method=use_direct_method, lookup=session)(url).content

    # Create a session outside of any cassette context manager
    session = requests.session()
    # Make a request to make sure that a connectionpool is instantiated
    request_func("GET", direct_method=use_direct_method, lookup=session)(httpbin_both + "/get")

    with vcr.use_cassette(str(tmpdir.join("session_created_outside.yaml"))):
        # These should only be the same if the patching succeeded.
        assert request_func("GET", direct_method=use_direct_method, lookup=session)(url).content == body


def test_nested_cassettes_with_session_created_before_nesting(httpbin_both, tmpdir, use_direct_method):
    """
    This tests ensures that a session that was created while one cassette was
    active is patched to the use the responses of a second cassette when it
    is enabled.
    """
    url = httpbin_both + "/bytes/1024"
    with vcr.use_cassette(str(tmpdir.join("first_nested.yaml"))):
        session = requests.session()
        first_body = request_func("GET", direct_method=use_direct_method, lookup=session)(url).content
        with vcr.use_cassette(str(tmpdir.join("second_nested.yaml"))):
            second_body = request_func("GET", direct_method=use_direct_method, lookup=session)(url).content
            third_body = request_func("GET", direct_method=use_direct_method)(url).content

    with vcr.use_cassette(str(tmpdir.join("second_nested.yaml"))):
        session = requests.session()
        assert (
            request_func("GET", direct_method=use_direct_method, lookup=session)(url).content == second_body
        )
        with vcr.use_cassette(str(tmpdir.join("first_nested.yaml"))):
            assert (
                request_func("GET", direct_method=use_direct_method, lookup=session)(url).content
                == first_body
            )
        assert request_func("GET", direct_method=use_direct_method, lookup=session)(url).content == third_body

    # Make sure that the session can now get content normally.
    assert (
        "User-agent"
        in request_func("GET", direct_method=use_direct_method, lookup=session)(
            httpbin_both.url + "/robots.txt"
        ).text
    )


def test_post_file(tmpdir, httpbin_both, use_direct_method):
    """Ensure that we handle posting a file."""
    url = httpbin_both + "/post"
    with vcr.use_cassette(str(tmpdir.join("post_file.yaml"))) as cass, open("tox.ini", "rb") as f:
        original_response = request_func("POST", direct_method=use_direct_method)(url, data=f).content

    # This also tests that we do the right thing with matching the body when they are files.
    with vcr.use_cassette(
        str(tmpdir.join("post_file.yaml")),
        match_on=("method", "scheme", "host", "port", "path", "query", "body"),
    ) as cass:
        with open("tox.ini", "rb") as f:
            tox_content = f.read()
        assert cass.requests[0].body.read() == tox_content
        with open("tox.ini", "rb") as f:
            new_response = request_func("POST", direct_method=use_direct_method)(url, data=f).content
        assert original_response == new_response


def test_filter_post_params(tmpdir, httpbin_both, use_direct_method):
    """
    This tests the issue in https://github.com/kevin1024/vcrpy/issues/158

    Ensure that a post request made through requests can still be filtered.
    with vcr.use_cassette(cass_file, filter_post_data_parameters=['id']) as cass:
        assert b'id=secret' not in cass.requests[0].body
    """
    url = httpbin_both.url + "/post"
    cass_loc = str(tmpdir.join("filter_post_params.yaml"))
    with vcr.use_cassette(cass_loc, filter_post_data_parameters=["key"]) as cass:
        request_func("POST", direct_method=use_direct_method)(url, data={"key": "value"})
    with vcr.use_cassette(cass_loc, filter_post_data_parameters=["key"]) as cass:
        assert b"key=value" not in cass.requests[0].body


def test_post_unicode_match_on_body(tmpdir, httpbin_both, use_direct_method):
    """Ensure that matching on POST body that contains Unicode characters works."""
    data = {"key1": "value1", "●‿●": "٩(●̮̮̃•̃)۶"}
    url = httpbin_both + "/post"

    with vcr.use_cassette(str(tmpdir.join("requests.yaml")), additional_matchers=("body",)):
        req1 = request_func("POST", direct_method=use_direct_method)(url, data=data).content

    with vcr.use_cassette(str(tmpdir.join("requests.yaml")), additional_matchers=("body",)):
        req2 = request_func("POST", direct_method=use_direct_method)(url, data=data).content

    assert req1 == req2
