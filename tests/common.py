# coding=utf-8

import os
import json
import shutil
import unittest


class TestVCR(unittest.TestCase):
    fixtures = os.path.join('does', 'not', 'exist')

    def tearDown(self):
        # Remove th urllib2 fixtures if they exist
        if os.path.exists(self.fixtures):
            shutil.rmtree(self.fixtures)

    def fixture(self, *names):
        '''Return a path to the provided fixture'''
        return os.path.join(self.fixtures, *names)

    def assertBodiesEqual(self, one, two):
        """
        httpbin.org returns a different `origin` header 
        each time, so strip this out since it makes testing
        difficult.
        """
        one, two = json.loads(one), json.loads(two)
        del one['origin']
        del two['origin']
        self.assertEqual(one, two)
