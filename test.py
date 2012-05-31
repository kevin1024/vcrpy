import os
import unittest
import vcr
import urllib2

TEST_CASSETTE_FILE = 'test/test_req.yaml'


class TestHttpRequest(unittest.TestCase):

    def setUp(self):
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
        with vcr.use_cassette('test/synopsis.yaml'):
            self.assertEqual(body, urllib2.urlopen('http://www.iana.org/domains/example/').read())
            self.assertEqual(body, urllib2.urlopen('http://www.iana.org/domains/example/').read())

    def test_response_headers(self):
        headers = urllib2.urlopen('http://www.iana.org/domains/example/').info()
        with vcr.use_cassette('test/synopsis.yaml'):
            self.assertEqual(headers, urllib2.urlopen('http://www.iana.org/domains/example/').info())
            self.assertEqual(headers, urllib2.urlopen('http://www.iana.org/domains/example/').info())


if __name__ == '__main__':
    unittest.main()
