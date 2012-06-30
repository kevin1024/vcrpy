import os
import unittest
import vcr
import urllib2

TEST_CASSETTE_FILE = 'test/test_req.yaml'


class TestHttpRequest(unittest.TestCase):

    def tearDown(self):
        try:
            os.remove(TEST_CASSETTE_FILE)
        except OSError:
            pass

    def test_response_code(self):
        code = urllib2.urlopen('http://www.iana.org/domains/example/').getcode()
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            self.assertEqual(code, urllib2.urlopen('http://www.iana.org/domains/example/').getcode())
            self.assertEqual(code, urllib2.urlopen('http://www.iana.org/domains/example/').getcode())

    def test_response_body(self):
        body = urllib2.urlopen('http://www.iana.org/domains/example/').read()
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            self.assertEqual(body, urllib2.urlopen('http://www.iana.org/domains/example/').read())
            self.assertEqual(body, urllib2.urlopen('http://www.iana.org/domains/example/').read())

    def test_response_headers(self):
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            headers = urllib2.urlopen('http://www.iana.org/domains/example/').info().items()
            self.assertEqual(headers, urllib2.urlopen('http://www.iana.org/domains/example/').info().items())

    def test_multiple_requests(self):
        body1 = urllib2.urlopen('http://www.iana.org/domains/example/').read()
	body2 = urllib2.urlopen('http://api.twitter.com/1/legal/tos.json').read()
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            self.assertEqual(body1, urllib2.urlopen('http://www.iana.org/domains/example/').read())
	    self.assertEqual(body2, urllib2.urlopen('http://api.twitter.com/1/legal/tos.json').read())
            self.assertEqual(body1, urllib2.urlopen('http://www.iana.org/domains/example/').read())
	    self.assertEqual(body2, urllib2.urlopen('http://api.twitter.com/1/legal/tos.json').read())


class TestHttps(unittest.TestCase):

    def tearDown(self):
        try:
            os.remove(TEST_CASSETTE_FILE)
        except OSError:
            pass
    
    def test_response_code(self):
        code = urllib2.urlopen('https://api.twitter.com/1/legal/tos.json').getcode()
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            self.assertEqual(code, urllib2.urlopen('https://api.twitter.com/1/legal/tos.json').getcode())
            self.assertEqual(code, urllib2.urlopen('https://api.twitter.com/1/legal/tos.json').getcode())

    def test_response_body(self):
        body = urllib2.urlopen('https://api.twitter.com/1/legal/tos.json').read()
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            self.assertEqual(body, urllib2.urlopen('https://api.twitter.com/1/legal/tos.json').read())
            self.assertEqual(body, urllib2.urlopen('https://api.twitter.com/1/legal/tos.json').read())

    def test_response_headers(self):
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            headers = urllib2.urlopen('https://api.twitter.com/1/legal/tos.json').info().items()
            self.assertEqual(headers, urllib2.urlopen('https://api.twitter.com/1/legal/tos.json').info().items())
   

if __name__ == '__main__':
    unittest.main()
