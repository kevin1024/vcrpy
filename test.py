# coding=utf-8
import os
import unittest
import vcr
from vcr.cassette import Cassette
import urllib2
from urllib import urlencode
import requests

TEST_CASSETTE_FILE = 'test/test_req.yaml'

class TestHttpRequest(unittest.TestCase):

    def tearDown(self):
        try:
            os.remove(TEST_CASSETTE_FILE)
        except OSError:
            pass

    def test_response_code(self):
        code = urllib2.urlopen('http://httpbin.org/').getcode()
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            self.assertEqual(code, urllib2.urlopen('http://httpbin.org/').getcode())
            self.assertEqual(code, urllib2.urlopen('http://httpbin.org/').getcode())

    def test_response_body(self):
        body = urllib2.urlopen('http://httpbin.org/').read()
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            self.assertEqual(body, urllib2.urlopen('http://httpbin.org/').read())
            self.assertEqual(body, urllib2.urlopen('http://httpbin.org/').read())

    def test_response_headers(self):
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            headers = urllib2.urlopen('http://httpbin.org/').info().items()
            self.assertEqual(headers, urllib2.urlopen('http://httpbin.org/').info().items())

    def test_multiple_requests(self):
        body1 = urllib2.urlopen('http://httpbin.org/').read()
        body2 = urllib2.urlopen('http://httpbin.org/get').read()
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            self.assertEqual(body1, urllib2.urlopen('http://httpbin.org/').read())
            self.assertEqual(body2, urllib2.urlopen('http://httpbin.org/get').read())
            self.assertEqual(body1, urllib2.urlopen('http://httpbin.org/').read())
            self.assertEqual(body2, urllib2.urlopen('http://httpbin.org/get').read())


class TestHttps(unittest.TestCase):

    def tearDown(self):
        try:
            os.remove(TEST_CASSETTE_FILE)
        except OSError:
            pass

    def test_response_code(self):
        code = urllib2.urlopen('https://httpbin.org/').getcode()
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            self.assertEqual(code, urllib2.urlopen('https://httpbin.org/').getcode())
            self.assertEqual(code, urllib2.urlopen('https://httpbin.org/').getcode())

    def test_response_body(self):
        body = urllib2.urlopen('https://httpbin.org/').read()
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            self.assertEqual(body, urllib2.urlopen('https://httpbin.org/').read())
            self.assertEqual(body, urllib2.urlopen('https://httpbin.org/').read())

    def test_response_headers(self):
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            headers = urllib2.urlopen('https://httpbin.org/').info().items()
            self.assertEqual(headers, urllib2.urlopen('https://httpbin.org/').info().items())

    def test_get_data(self):
        TEST_DATA = urlencode({'some': 1, 'data': 'here'})
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            body = urllib2.urlopen('https://httpbin.org/get?' + TEST_DATA).read()
            self.assertEqual(body, urllib2.urlopen('https://httpbin.org/get?' + TEST_DATA).read())

    def test_post_data(self):
        TEST_DATA = urlencode({'some': 1, 'data': 'here'})
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            body = urllib2.urlopen('https://httpbin.org/post', TEST_DATA).read()
            self.assertEqual(body, urllib2.urlopen('https://httpbin.org/post', TEST_DATA).read())

    def test_post_unicode(self):
        TEST_DATA = urlencode({'snowman': u'☃'.encode('utf-8')})
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            body = urllib2.urlopen('https://httpbin.org/post', TEST_DATA).read()
            self.assertEqual(body, urllib2.urlopen('https://httpbin.org/post', TEST_DATA).read())


class TestCassette(unittest.TestCase):
    def test_serialize_cassette(self):
        c1 = Cassette()
        c1.requests = ['a', 'b', 'c']
        c1.responses = ['d', 'e', 'f']
        ser = c1.serialize()
        c2 = Cassette(ser)
        self.assertEqual(c1.requests, c2.requests)
        self.assertEqual(c1.responses, c2.responses)

class TestRequestsGet(unittest.TestCase):

    def setUp(self):
        self.unmolested_response = requests.get('http://httpbin.org/')
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            self.initial_response = requests.get('http://httpbin.org/')
            self.cached_response = requests.get('http://httpbin.org/')

    def tearDown(self):
        try:
            os.remove(TEST_CASSETTE_FILE)
        except OSError:
            pass

    def test_initial_response_code(self):
        self.assertEqual(self.unmolested_response.status_code, self.initial_response.status_code)

    def test_cached_response_code(self):
        self.assertEqual(self.unmolested_response.status_code, self.cached_response.status_code)

    def test_initial_response_headers(self):
        self.assertEqual(self.unmolested_response.headers['content-type'], self.initial_response.headers['content-type'])

    def test_cached_response_headers(self):
        self.assertEqual(self.unmolested_response.headers['content-type'], self.cached_response.headers['content-type'])

    def test_initial_response_text(self):
        self.assertEqual(self.unmolested_response.text, self.initial_response.text)

    def test_cached_response_text(self):
        self.assertEqual(self.unmolested_response.text, self.cached_response.text)

class TestRequestsPost(unittest.TestCase):
    def setUp(self):
        payload = {'key1': 'value1', 'key2': 'value2'}
        self.unmolested_response = requests.post('http://httpbin.org/post', payload)
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            self.initial_response = requests.post('http://httpbin.org/post', payload)
            self.cached_response = requests.post('http://httpbin.org/post', payload)

    def tearDown(self):
        try:
            os.remove(TEST_CASSETTE_FILE)
        except OSError:
            pass

    def test_initial_post_response_text(self):
        self.assertEqual(self.unmolested_response.text, self.initial_response.text)

    def test_cached_post_response_text(self):
        self.assertEqual(self.unmolested_response.text, self.cached_response.text)

class TestRequestsHTTPS(unittest.TestCase):
    def setUp(self):
        self.unmolested_response = requests.get('https://github.com')
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            self.initial_response = requests.get('https://github.com')
            self.cached_response = requests.get('https://github.com')

    def tearDown(self):
        try:
            os.remove(TEST_CASSETTE_FILE)
        except OSError:
            pass

    def test_initial_https_response_text(self):
        self.assertEqual(self.unmolested_response.text, self.initial_response.text)

    def test_cached_https_response_text(self):
        self.assertEqual(self.unmolested_response.text, self.cached_response.text)

    


if __name__ == '__main__':
    unittest.main()
