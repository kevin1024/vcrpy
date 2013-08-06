'''Test requests' interaction with vcr'''

# coding=utf-8

# Internal imports
import vcr
from .common import TestVCR

import os
import pytest
requests = pytest.importorskip("requests")


class TestRequestsBase(TestVCR):
    '''Some utility for running Requests tests'''
    fixtures = os.path.join('tests', 'fixtures', 'requests')


class TestHTTPRequests(TestRequestsBase):
    '''Some tests using requests and http'''
    scheme = 'http'

    def test_status_code(self):
        '''Ensure that we can read the status code'''
        url = self.scheme + '://httpbin.org/'
        with vcr.use_cassette(self.fixture('atts.yaml')) as cass:
            # Ensure that this is empty to begin with
            self.assertEqual(len(cass), 0)
            self.assertEqual(cass.play_count, 0)
            self.assertEqual(
                requests.get(url).status_code,
                requests.get(url).status_code)
            # Ensure that we've now cached a single response
            self.assertEqual(len(cass), 1)
            self.assertEqual(cass.play_count, 1)

    def test_headers(self):
        '''Ensure that we can read the headers back'''
        url = self.scheme + '://httpbin.org/'
        with vcr.use_cassette(self.fixture('headers.yaml')) as cass:
            # Ensure that this is empty to begin with
            self.assertEqual(len(cass), 0)
            self.assertEqual(cass.play_count, 0)
            self.assertEqual(
                requests.get(url).headers,
                requests.get(url).headers)
            # Ensure that we've now cached a single response
            self.assertEqual(len(cass), 1)
            self.assertEqual(cass.play_count, 1)

    def test_body(self):
        '''Ensure the responses are all identical enough'''
        url = self.scheme + '://httpbin.org/bytes/1024'
        with vcr.use_cassette(self.fixture('body.yaml')) as cass:
            # Ensure that this is empty to begin with
            self.assertEqual(len(cass), 0)
            self.assertEqual(cass.play_count, 0)
            self.assertEqual(
                requests.get(url).content,
                requests.get(url).content)
            # Ensure that we've now cached a single response
            self.assertEqual(len(cass), 1)
            self.assertEqual(cass.play_count, 1)

    def test_auth(self):
        '''Ensure that we can handle basic auth'''
        auth = ('user', 'passwd')
        url = self.scheme + '://httpbin.org/basic-auth/user/passwd'
        with vcr.use_cassette(self.fixture('auth.yaml')) as cass:
            # Ensure that this is empty to begin with
            self.assertEqual(len(cass), 0)
            self.assertEqual(cass.play_count, 0)
            one = requests.get(url, auth=auth)
            two = requests.get(url, auth=auth)
            self.assertEqual(one.content, two.content)
            self.assertEqual(one.status_code, two.status_code)
            # Ensure that we've now cached a single response
            self.assertEqual(len(cass), 1)
            self.assertEqual(cass.play_count, 1)

    def test_auth_failed(self):
        '''Ensure that we can save failed auth statuses'''
        auth = ('user', 'wrongwrongwrong')
        url = self.scheme + '://httpbin.org/basic-auth/user/passwd'
        with vcr.use_cassette(self.fixture('auth-failed.yaml')) as cass:
            # Ensure that this is empty to begin with
            self.assertEqual(len(cass), 0)
            self.assertEqual(cass.play_count, 0)
            one = requests.get(url, auth=auth)
            two = requests.get(url, auth=auth)
            self.assertEqual(one.content, two.content)
            self.assertEqual(one.status_code, two.status_code)
            self.assertNotEqual(one.status_code, 200)
            # Ensure that we've now cached a single response
            self.assertEqual(len(cass), 1)
            self.assertEqual(cass.play_count, 1)

    def test_post(self):
        '''Ensure that we can post and cache the results'''
        data = {'key1': 'value1', 'key2': 'value2'}
        url = self.scheme + '://httpbin.org/post'
        with vcr.use_cassette(self.fixture('redirect.yaml')) as cass:
            # Ensure that this is empty to begin with
            self.assertEqual(len(cass), 0)
            self.assertEqual(cass.play_count, 0)
            self.assertEqual(
                requests.post(url, data).content,
                requests.post(url, data).content)
            # Ensure that we've now cached a single response
            self.assertEqual(len(cass), 1)
            self.assertEqual(cass.play_count, 1)

    def test_redirects(self):
        '''Ensure that we can handle redirects'''
        url = self.scheme + '://httpbin.org/redirect-to?url=bytes/1024'
        with vcr.use_cassette(self.fixture('redirect.yaml')) as cass:
            # Ensure that this is empty to begin with
            self.assertEqual(len(cass), 0)
            self.assertEqual(cass.play_count, 0)
            self.assertEqual(
                requests.get(url).content,
                requests.get(url).content)
            # Ensure that we've now cached /two/ responses. One for the redirect
            # and one for the final fetch
            self.assertEqual(len(cass), 2)
            self.assertEqual(cass.play_count, 2)


class TestHTTPSRequests(TestHTTPRequests):
    '''Same as above, now in https'''
    scheme = 'https'

    def test_cross_scheme(self):
        '''Ensure that requests between schemes are treated separately'''
        # First fetch a url under http, and then again under https and then
        # ensure that we haven't served anything out of cache, and we have two
        # requests / response pairs in the cassette
        with vcr.use_cassette(self.fixture('cross_scheme.yaml')) as cass:
            requests.get('https://httpbin.org/')
            requests.get('http://httpbin.org/')
            self.assertEqual(len(cass), 2)
            self.assertEqual(cass.play_count, 0)


class TestWild(TestRequestsBase):
    '''Test some examples from the wild'''
    fixtures = os.path.join('tests', 'fixtures', 'wild')

    def tearDown(self):
        # No deleting our directory, and ensure that it exists
        self.assertTrue(os.path.exists(self.fixture()))

    def test_domain_redirect(self):
        '''Ensure that redirects across domains are considered unique'''
        # In this example, seomoz.org redirects to moz.com, and if those
        # requests are considered identical, then we'll be stuck in a redirect
        # loop.
        url = 'http://seomoz.org/'
        with vcr.use_cassette(self.fixture('domain_redirect.yaml')) as cass:
            requests.get(url, headers={'User-Agent': 'vcrpy-test'})
            # Ensure that we've now served two responses. One for the original
            # redirect, and a second for the actual fetch
            self.assertEqual(cass.play_count, 2)
