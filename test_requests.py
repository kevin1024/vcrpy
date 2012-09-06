# coding=utf-8
import os
import unittest
import vcr
import requests

TEST_CASSETTE_FILE = 'cassettes/test_req.yaml'


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


class TestRequestsAuth(unittest.TestCase):

    def setUp(self):
        self.unmolested_response = requests.get('https://httpbin.org/basic-auth/user/passwd', auth=('user', 'passwd'))
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            self.initial_response = requests.get('https://httpbin.org/basic-auth/user/passwd', auth=('user', 'passwd'))
            self.cached_response = requests.get('https://httpbin.org/basic-auth/user/passwd', auth=('user', 'passwd'))

    def tearDown(self):
        try:
            os.remove(TEST_CASSETTE_FILE)
        except OSError:
            pass

    def test_initial_response_code(self):
        self.assertEqual(self.unmolested_response.status_code, self.initial_response.status_code)

    def test_cached_response_code(self):
        self.assertEqual(self.unmolested_response.status_code, self.cached_response.status_code)

    def test_cached_response_auth_can_fail(self):
        auth_fail_cached = requests.get('https://httpbin.org/basic-auth/user/passwd', auth=('user', 'passwdzzz'))
        self.assertNotEqual(self.unmolested_response.status_code, auth_fail_cached.status_code)


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
    maxDiff = None

    def setUp(self):
        self.unmolested_response = requests.get('https://httpbin.org/get')
        with vcr.use_cassette(TEST_CASSETTE_FILE):
            self.initial_response = requests.get('https://httpbin.org/get')
            self.cached_response = requests.get('https://httpbin.org/get')

    def tearDown(self):
        try:
            os.remove(TEST_CASSETTE_FILE)
        except OSError:
            pass

    def test_initial_https_response_text(self):
        self.assertEqual(self.unmolested_response.text, self.initial_response.text)

    def test_cached_https_response_text(self):
        self.assertEqual(self.unmolested_response.text, self.cached_response.text)
