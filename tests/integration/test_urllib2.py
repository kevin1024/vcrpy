'''Integration tests with urllib2'''
# coding=utf-8

# Internal imports
import vcr
from .common import TestVCR

# Testing urllib2 fetching
import os
import urllib2
from urllib import urlencode


class TestUrllib2(TestVCR):
    '''Base class for tests for urllib2'''
    fixtures = os.path.join('tests', 'fixtures', 'urllib2')


class TestUrllib2Http(TestUrllib2):
    '''Tests for integration with urllib2'''
    scheme = 'http'

    def test_response_code(self):
        '''Ensure we can read a response code from a fetch'''
        url = self.scheme + '://httpbin.org/'
        with vcr.use_cassette(self.fixture('atts.yaml')) as cass:
            # Ensure that this is empty to begin with
            self.assertEqual(len(cass), 0)
            self.assertEqual(len(cass.cached()), 0)
            self.assertEqual(
                urllib2.urlopen(url).getcode(),
                urllib2.urlopen(url).getcode())
            # Ensure that we've now cached a single response
            self.assertEqual(len(cass), 1)
            self.assertEqual(len(cass.cached()), 1)

    def test_random_body(self):
        '''Ensure we can read the content, and that it's served from cache'''
        url = self.scheme + '://httpbin.org/bytes/1024'
        with vcr.use_cassette(self.fixture('body.yaml')) as cass:
            # Ensure that this is empty to begin with
            self.assertEqual(len(cass), 0)
            self.assertEqual(len(cass.cached()), 0)
            self.assertEqual(
                urllib2.urlopen(url).read(),
                urllib2.urlopen(url).read())
            # Ensure that we've now cached a single response
            self.assertEqual(len(cass), 1)
            self.assertEqual(len(cass.cached()), 1)

    def test_response_headers(self):
        '''Ensure we can get information from the response'''
        url = self.scheme + '://httpbin.org/'
        with vcr.use_cassette(self.fixture('headers.yaml')) as cass:
            # Ensure that this is empty to begin with
            self.assertEqual(len(cass), 0)
            self.assertEqual(len(cass.cached()), 0)
            self.assertEqual(
                urllib2.urlopen(url).info().items(),
                urllib2.urlopen(url).info().items())
            # Ensure that we've now cached a single response
            self.assertEqual(len(cass), 1)

    def test_multiple_requests(self):
        '''Ensure that we can cache multiple requests'''
        urls = [
            self.scheme + '://httpbin.org/',
            self.scheme + '://httpbin.org/get',
            self.scheme + '://httpbin.org/bytes/1024'
        ]
        with vcr.use_cassette(self.fixture('multiple.yaml')) as cass:
            for index in range(len(urls)):
                url = urls[index]
                self.assertEqual(len(cass), index)
                self.assertEqual(len(cass.cached()), index)
                self.assertEqual(
                    urllib2.urlopen(url).read(),
                    urllib2.urlopen(url).read())
                self.assertEqual(len(cass), index + 1)
                self.assertEqual(len(cass.cached()), index + 1)

    def test_get_data(self):
        '''Ensure that it works with query data'''
        data = urlencode({'some': 1, 'data': 'here'})
        url = self.scheme + '://httpbin.org/get?' + data
        with vcr.use_cassette(self.fixture('get_data.yaml')) as cass:
            # Ensure that this is empty to begin with
            self.assertEqual(len(cass), 0)
            self.assertEqual(len(cass.cached()), 0)
            self.assertEqual(
                urllib2.urlopen(url).read(),
                urllib2.urlopen(url).read())
            # Ensure that we've now cached a single response
            self.assertEqual(len(cass), 1)
            self.assertEqual(len(cass.cached()), 1)

    def test_post_data(self):
        '''Ensure that it works when posting data'''
        data = urlencode({'some': 1, 'data': 'here'})
        url = self.scheme + '://httpbin.org/post'
        with vcr.use_cassette(self.fixture('post_data.yaml')) as cass:
            # Ensure that this is empty to begin with
            self.assertEqual(len(cass), 0)
            self.assertEqual(len(cass.cached()), 0)
            self.assertEqual(
                urllib2.urlopen(url, data).read(),
                urllib2.urlopen(url, data).read())
            # Ensure that we've now cached a single response
            self.assertEqual(len(cass), 1)
            self.assertEqual(len(cass.cached()), 1)

    def test_post_unicode_data(self):
        '''Ensure that it works when posting unicode data'''
        data = urlencode({'snowman': u'☃'.encode('utf-8')})
        url = self.scheme + '://httpbin.org/post'
        with vcr.use_cassette(self.fixture('post_data.yaml')) as cass:
            # Ensure that this is empty to begin with
            self.assertEqual(len(cass), 0)
            self.assertEqual(len(cass.cached()), 0)
            self.assertEqual(
                urllib2.urlopen(url, data).read(),
                urllib2.urlopen(url, data).read())
            # Ensure that we've now cached a single response
            self.assertEqual(len(cass), 1)
            self.assertEqual(len(cass.cached()), 1)


class TestUrllib2Https(TestUrllib2Http):
    '''Similar tests but for http status codes'''
    scheme = 'https'

    def test_cross_scheme(self):
        '''Ensure that requests between schemes are treated separately'''
        # First fetch a url under https, and then again under https and then
        # ensure that we haven't served anything out of cache, and we have two
        # requests / response pairs in the cassette
        with vcr.use_cassette(self.fixture('cross_scheme.yaml')) as cass:
            urllib2.urlopen('https://httpbin.org/')
            urllib2.urlopen('http://httpbin.org/')
            self.assertEqual(len(cass), 2)
            self.assertEqual(len(cass.cached()), 0)
