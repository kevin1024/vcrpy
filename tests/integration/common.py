# coding=utf-8

import os
import shutil
import unittest


class TestVCR(unittest.TestCase):
    fixtures = os.path.join('does', 'not', 'exist')

    def tearDown(self):
        # Remove the fixtures if they exist
        if os.path.exists(self.fixtures):
            shutil.rmtree(self.fixtures)

    def fixture(self, *names):
        '''Return a path to the provided fixture'''
        return os.path.join(self.fixtures, *names)
