# coding=utf-8
import os
import unittest
import vcr
from vcr.cassette import Cassette
import urllib2
from urllib import urlencode

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
        TEST_DATA = urlencode({'some':1,'data':'here'})
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            body = urllib2.urlopen('https://httpbin.org/get?' + TEST_DATA).read()
            self.assertEqual(body, urllib2.urlopen('https://httpbin.org/get?' + TEST_DATA).read())

    def test_post_data(self):
        TEST_DATA = urlencode({'some':1,'data':'here'})
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            body = urllib2.urlopen('https://httpbin.org/post',TEST_DATA).read()
            self.assertEqual(body, urllib2.urlopen('https://httpbin.org/post',TEST_DATA).read())

    def test_post_unicode(self):
        TEST_DATA = urlencode({'snowman':u'☃'.encode('utf-8')})
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            body = urllib2.urlopen('https://httpbin.org/post',TEST_DATA).read()
            self.assertEqual(body, urllib2.urlopen('https://httpbin.org/post',TEST_DATA).read())

class TestCassette(unittest.TestCase):
    def test_serialize_cassette(self):
        c1 = Cassette()
	c1.requests = ['a','b','c']
	c1.responses = ['d','e','f']
	ser = c1.serialize()
	c2 = Cassette(ser)
	self.assertEqual(c1.requests,c2.requests)
	self.assertEqual(c1.responses,c2.responses)




if __name__ == '__main__':
    unittest.main()
