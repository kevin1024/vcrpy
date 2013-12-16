'''Integration tests with urllib2'''
# coding=utf-8

# External imports
import os
import urllib2
from urllib import urlencode
import pytest

# Internal imports
import vcr

from assertions import assert_cassette_empty, assert_cassette_has_one_response


@pytest.fixture(params=["https", "http"])
def scheme(request):
    """
    Fixture that returns both http and https
    """
    return request.param


def test_response_code(scheme, tmpdir):
    '''Ensure we can read a response code from a fetch'''
    url = scheme + '://httpbin.org/'
    with vcr.use_cassette(str(tmpdir.join('atts.yaml'))) as cass:
        code = urllib2.urlopen(url).getcode()

    with vcr.use_cassette(str(tmpdir.join('atts.yaml'))) as cass:
        assert code == urllib2.urlopen(url).getcode()


def test_random_body(scheme, tmpdir):
    '''Ensure we can read the content, and that it's served from cache'''
    url = scheme + '://httpbin.org/bytes/1024'
    with vcr.use_cassette(str(tmpdir.join('body.yaml'))) as cass:
        body = urllib2.urlopen(url).read()

    with vcr.use_cassette(str(tmpdir.join('body.yaml'))) as cass:
        assert body == urllib2.urlopen(url).read()


def test_response_headers(scheme, tmpdir):
    '''Ensure we can get information from the response'''
    url = scheme + '://httpbin.org/'
    with vcr.use_cassette(str(tmpdir.join('headers.yaml'))) as cass:
        open1 = urllib2.urlopen(url).info().items()

    with vcr.use_cassette(str(tmpdir.join('headers.yaml'))) as cass:
        open2 = urllib2.urlopen(url).info().items()
        assert open1 == open2


def test_multiple_requests(scheme, tmpdir):
    '''Ensure that we can cache multiple requests'''
    urls = [
        scheme + '://httpbin.org/',
        scheme + '://httpbin.org/',
        scheme + '://httpbin.org/get',
        scheme + '://httpbin.org/bytes/1024'
    ]
    with vcr.use_cassette(str(tmpdir.join('multiple.yaml'))) as cass:
        map(urllib2.urlopen, urls)
    assert len(cass) == len(urls)


def test_get_data(scheme, tmpdir):
    '''Ensure that it works with query data'''
    data = urlencode({'some': 1, 'data': 'here'})
    url = scheme + '://httpbin.org/get?' + data
    with vcr.use_cassette(str(tmpdir.join('get_data.yaml'))) as cass:
        res1 = urllib2.urlopen(url).read()

    with vcr.use_cassette(str(tmpdir.join('get_data.yaml'))) as cass:
        res2 = urllib2.urlopen(url).read()

    assert res1 == res2


def test_post_data(scheme, tmpdir):
    '''Ensure that it works when posting data'''
    data = urlencode({'some': 1, 'data': 'here'})
    url = scheme + '://httpbin.org/post'
    with vcr.use_cassette(str(tmpdir.join('post_data.yaml'))) as cass:
        res1 = urllib2.urlopen(url, data).read()

    with vcr.use_cassette(str(tmpdir.join('post_data.yaml'))) as cass:
        res2 = urllib2.urlopen(url, data).read()

    assert res1 == res2
    assert_cassette_has_one_response(cass)


def test_post_unicode_data(scheme, tmpdir):
    '''Ensure that it works when posting unicode data'''
    data = urlencode({'snowman': u'☃'.encode('utf-8')})
    url = scheme + '://httpbin.org/post'
    with vcr.use_cassette(str(tmpdir.join('post_data.yaml'))) as cass:
        res1 = urllib2.urlopen(url, data).read()
    with vcr.use_cassette(str(tmpdir.join('post_data.yaml'))) as cass:
        res2 = urllib2.urlopen(url, data).read()
    assert res1 == res2
    assert_cassette_has_one_response(cass)


def test_cross_scheme(tmpdir):
    '''Ensure that requests between schemes are treated separately'''
    # First fetch a url under https, and then again under https and then
    # ensure that we haven't served anything out of cache, and we have two
    # requests / response pairs in the cassette
    with vcr.use_cassette(str(tmpdir.join('cross_scheme.yaml'))) as cass:
        urllib2.urlopen('https://httpbin.org/')
        urllib2.urlopen('http://httpbin.org/')
        assert len(cass) == 2
        assert cass.play_count == 0

def test_decorator(scheme, tmpdir):
    '''Test the decorator version of VCR.py'''
    url = scheme + '://httpbin.org/'

    @vcr.use_cassette(str(tmpdir.join('atts.yaml')))
    def inner1():
        return urllib2.urlopen(url).getcode()

    @vcr.use_cassette(str(tmpdir.join('atts.yaml')))
    def inner2():
        return urllib2.urlopen(url).getcode()

    assert inner1() == inner2()
