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
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            code = urllib2.urlopen('http://www.iana.org/domains/example/').getcode()
            self.assertEqual(code,urllib2.urlopen('http://www.iana.org/domains/example/').getcode())

    def test_response_body(self):
        with vcr.use_cassette('test/synopsis.yaml'):
            body = urllib2.urlopen('http://www.iana.org/domains/example/').read()
            self.assertEqual(body,urllib2.urlopen('http://www.iana.org/domains/example/').read())


if __name__ == '__main__':
    unittest.main()
