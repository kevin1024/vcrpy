'''Basic tests about cassettes'''
# coding=utf-8

# Internal imports
import vcr
from .common import TestVCR

# External imports
import os
import urllib2


class TestCassette(TestVCR):
    '''We should be able to save a cassette'''
    fixtures = os.path.join('tests', 'fixtures', 'basic')

    def test_nonexistent_directory(self):
        '''If we load a cassette in a nonexistent directory, it can save ok'''
        self.assertFalse(os.path.exists(self.fixture('nonexistent')))
        with vcr.use_cassette(self.fixture('nonexistent', 'cass.yaml')):
            urllib2.urlopen('http://httpbin.org/').read()
        # This should have made the file and the directory
        self.assertTrue(
            os.path.exists(self.fixture('nonexistent', 'cass.yaml')))

    def test_unpatch(self):
        '''Ensure that our cassette gets unpatched when we're done'''
        with vcr.use_cassette(self.fixture('unpatch.yaml')) as cass:
            urllib2.urlopen('http://httpbin.org/').read()

        # Make the same requests, and assert that we haven't served any more
        # requests out of cache
        urllib2.urlopen('http://httpbin.org/').read()
        self.assertEqual(cass.play_count, 0)
