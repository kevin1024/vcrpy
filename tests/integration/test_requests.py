'''Test requests' interaction with vcr'''

# coding=utf-8

import os
import pytest
import vcr
from assertions import assert_cassette_empty, assert_cassette_has_one_response
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
        # Ensure that this is empty to begin with
        assert_cassette_empty(cass)
        assert requests.get(url).status_code == requests.get(url).status_code
        # Ensure that we've now cached a single response
        assert_cassette_has_one_response(cass)


def test_headers(scheme, tmpdir):
    '''Ensure that we can read the headers back'''
    url = scheme + '://httpbin.org/'
    with vcr.use_cassette(str(tmpdir.join('headers.yaml'))) as cass:
        # Ensure that this is empty to begin with
        assert_cassette_empty(cass)
        assert requests.get(url).headers == requests.get(url).headers
        # Ensure that we've now cached a single response
        assert_cassette_has_one_response(cass)


def test_body(tmpdir, scheme):
    '''Ensure the responses are all identical enough'''
    url = scheme + '://httpbin.org/bytes/1024'
    with vcr.use_cassette(str(tmpdir.join('body.yaml'))) as cass:
        # Ensure that this is empty to begin with
        assert_cassette_empty(cass)
        assert requests.get(url).content == requests.get(url).content
        # Ensure that we've now cached a single response
        assert_cassette_has_one_response(cass)


def test_auth(tmpdir, scheme):
    '''Ensure that we can handle basic auth'''
    auth = ('user', 'passwd')
    url = scheme + '://httpbin.org/basic-auth/user/passwd'
    with vcr.use_cassette(str(tmpdir.join('auth.yaml'))) as cass:
        # Ensure that this is empty to begin with
        assert_cassette_empty(cass)
        one = requests.get(url, auth=auth)
        two = requests.get(url, auth=auth)
        assert one.content == two.content
        assert one.status_code == two.status_code
        # Ensure that we've now cached a single response
        assert_cassette_has_one_response(cass)


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
        # Ensure that we've now cached a single response
        assert_cassette_has_one_response(cass)


def test_post(tmpdir, scheme):
    '''Ensure that we can post and cache the results'''
    data = {'key1': 'value1', 'key2': 'value2'}
    url = scheme + '://httpbin.org/post'
    with vcr.use_cassette(str(tmpdir.join('requests.yaml'))) as cass:
        # Ensure that this is empty to begin with
        assert_cassette_empty(cass)
        req1 = requests.post(url, data).content
        req2 = requests.post(url, data).content
        assert req1 == req2
        # Ensure that we've now cached a single response
        assert_cassette_has_one_response(cass)


def test_redirects(tmpdir, scheme):
    '''Ensure that we can handle redirects'''
    url = scheme + '://httpbin.org/redirect-to?url=bytes/1024'
    with vcr.use_cassette(str(tmpdir.join('requests.yaml'))) as cass:
        # Ensure that this is empty to begin with
        assert_cassette_empty(cass)
        assert requests.get(url).content == requests.get(url).content
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
    '''Ensure the responses are all identical enough'''
    url = scheme + '://httpbin.org/gzip'
    with vcr.use_cassette(str(tmpdir.join('gzip.yaml'))) as cass:
        # Ensure that this is empty to begin with
        assert_cassette_empty(cass)
        # assert the content comes back as json
        response = requests.get(url)
        assert response.content.strip()[0] == '{'
        assert response.content.strip()[-1] == '}'
        assert response.content == requests.get(url).content
        # Ensure that we've now cached a single response
        assert_cassette_has_one_response(cass)
