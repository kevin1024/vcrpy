'''Test requests' interaction with vcr'''

# coding=utf-8

import os
import pytest
import vcr
from assertions import (
    assert_cassette_empty,
    assert_cassette_has_one_response,
    assert_is_json
)
requests = pytest.importorskip("requests")


@pytest.fixture(params=["https", "http"])
def scheme(request):
    """
    Fixture that returns both http and https
    """
    return request.param


def test_status_code(scheme, tmpdir):
    '''Ensure that we can read the status code'''
    url = scheme + '://httpbin.org/'
    with vcr.use_cassette(str(tmpdir.join('atts.yaml'))) as cass:
        status_code = requests.get(url).status_code

    with vcr.use_cassette(str(tmpdir.join('atts.yaml'))) as cass:
        assert status_code == requests.get(url).status_code


def test_headers(scheme, tmpdir):
    '''Ensure that we can read the headers back'''
    url = scheme + '://httpbin.org/'
    with vcr.use_cassette(str(tmpdir.join('headers.yaml'))) as cass:
        headers = requests.get(url).headers

    with vcr.use_cassette(str(tmpdir.join('headers.yaml'))) as cass:
        assert headers == requests.get(url).headers


def test_body(tmpdir, scheme):
    '''Ensure the responses are all identical enough'''
    url = scheme + '://httpbin.org/bytes/1024'
    with vcr.use_cassette(str(tmpdir.join('body.yaml'))) as cass:
        content = requests.get(url).content

    with vcr.use_cassette(str(tmpdir.join('body.yaml'))) as cass:
        assert content == requests.get(url).content


def test_auth(tmpdir, scheme):
    '''Ensure that we can handle basic auth'''
    auth = ('user', 'passwd')
    url = scheme + '://httpbin.org/basic-auth/user/passwd'
    with vcr.use_cassette(str(tmpdir.join('auth.yaml'))) as cass:
        one = requests.get(url, auth=auth)

    with vcr.use_cassette(str(tmpdir.join('auth.yaml'))) as cass:
        two = requests.get(url, auth=auth)
        assert one.content == two.content
        assert one.status_code == two.status_code


def test_auth_failed(tmpdir, scheme):
    '''Ensure that we can save failed auth statuses'''
    auth = ('user', 'wrongwrongwrong')
    url = scheme + '://httpbin.org/basic-auth/user/passwd'
    with vcr.use_cassette(str(tmpdir.join('auth-failed.yaml'))) as cass:
        # Ensure that this is empty to begin with
        assert_cassette_empty(cass)
        one = requests.get(url, auth=auth)
        two = requests.get(url, auth=auth)
        assert one.content == two.content
        assert one.status_code == two.status_code == 401


def test_post(tmpdir, scheme):
    '''Ensure that we can post and cache the results'''
    data = {'key1': 'value1', 'key2': 'value2'}
    url = scheme + '://httpbin.org/post'
    with vcr.use_cassette(str(tmpdir.join('requests.yaml'))) as cass:
        req1 = requests.post(url, data).content

    with vcr.use_cassette(str(tmpdir.join('requests.yaml'))) as cass:
        req2 = requests.post(url, data).content

    assert req1 == req2


def test_redirects(tmpdir, scheme):
    '''Ensure that we can handle redirects'''
    url = scheme + '://httpbin.org/redirect-to?url=bytes/1024'
    with vcr.use_cassette(str(tmpdir.join('requests.yaml'))) as cass:
        content = requests.get(url).content

    with vcr.use_cassette(str(tmpdir.join('requests.yaml'))) as cass:
        assert content == requests.get(url).content
        # Ensure that we've now cached *two* responses. One for the redirect
        # and one for the final fetch
        assert len(cass) == 2
        assert cass.play_count == 2


def test_cross_scheme(tmpdir, scheme):
    '''Ensure that requests between schemes are treated separately'''
    # First fetch a url under http, and then again under https and then
    # ensure that we haven't served anything out of cache, and we have two
    # requests / response pairs in the cassette
    with vcr.use_cassette(str(tmpdir.join('cross_scheme.yaml'))) as cass:
        requests.get('https://httpbin.org/')
        requests.get('http://httpbin.org/')
        assert cass.play_count == 0
        assert len(cass) == 2


def test_gzip(tmpdir, scheme):
    '''
    Ensure that requests (actually urllib3) is able to automatically decompress
    the response body
    '''
    url = scheme + '://httpbin.org/gzip'
    response = requests.get(url)

    with vcr.use_cassette(str(tmpdir.join('gzip.yaml'))) as cass:
        response = requests.get(url)
        assert_is_json(response.content)

    with vcr.use_cassette(str(tmpdir.join('gzip.yaml'))) as cass:
        assert_is_json(response.content)


def test_session_and_connection_close(tmpdir, scheme):
    '''
    This tests the issue in https://github.com/kevin1024/vcrpy/issues/48

    If you use a requests.session and the connection is closed, then an
    exception is raised in the urllib3 module vendored into requests:
    `AttributeError: 'NoneType' object has no attribute 'settimeout'`
    '''
    with vcr.use_cassette(str(tmpdir.join('session_connection_closed.yaml'))):
        session = requests.session()

        resp = session.get('http://httpbin.org/get', headers={'Connection': 'close'})
        resp = session.get('http://httpbin.org/get', headers={'Connection': 'close'})
