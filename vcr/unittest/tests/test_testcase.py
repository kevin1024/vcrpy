from __future__ import absolute_import, unicode_literals

import os
from mock import MagicMock as Mock
from unittest import defaultTestLoader, TextTestRunner
from vcr_unittest import VCRTestCase

try:
    from urllib2 import urlopen
except ImportError:
    from urllib.request import urlopen


def test_defaults():

    class MyTest(VCRTestCase):
        def test_foo(self):
            pass

    test = run_testcase(MyTest)[0][0]
    expected_path = os.path.join(os.path.dirname(__file__), 'cassettes')
    expected_name = 'MyTest.test_foo.yaml'
    assert os.path.dirname(test.cassette._path) == expected_path
    assert os.path.basename(test.cassette._path) == expected_name


def test_disabled():

    # Baseline vcr_enabled = True
    class MyTest(VCRTestCase):
        def test_foo(self):
            pass
    test = run_testcase(MyTest)[0][0]
    assert hasattr(test, 'cassette')

    # Test vcr_enabled = False
    class MyTest(VCRTestCase):
        vcr_enabled = False
        def test_foo(self):
            pass
    test = run_testcase(MyTest)[0][0]
    assert not hasattr(test, 'cassette')


def test_cassette_library_dir():

    class MyTest(VCRTestCase):
        def test_foo(self):
            pass
        def _get_cassette_library_dir(self):
            return '/testing'

    test = run_testcase(MyTest)[0][0]
    assert test.cassette._path.startswith('/testing/')


def test_cassette_name():

    class MyTest(VCRTestCase):
        def test_foo(self):
            pass
        def _get_cassette_name(self):
            return 'my-custom-name'

    test = run_testcase(MyTest)[0][0]
    assert os.path.basename(test.cassette._path) == 'my-custom-name'


def test_vcr_kwargs_overridden():

    class MyTest(VCRTestCase):
        def test_foo(self):
            pass
        def _get_vcr_kwargs(self):
            kwargs = super(MyTest, self)._get_vcr_kwargs()
            kwargs['record_mode'] = 'new_episodes'
            return kwargs

    test = run_testcase(MyTest)[0][0]
    assert test.cassette.record_mode == 'new_episodes'


def test_vcr_kwargs_passed():

    class MyTest(VCRTestCase):
        def test_foo(self):
            pass
        def _get_vcr_kwargs(self):
            return super(MyTest, self)._get_vcr_kwargs(
                record_mode='new_episodes',
            )

    test = run_testcase(MyTest)[0][0]
    assert test.cassette.record_mode == 'new_episodes'


def test_vcr_kwargs_cassette_dir():

    # Test that _get_cassette_library_dir applies if cassette_library_dir
    # is absent from vcr kwargs.
    class MyTest(VCRTestCase):
        def test_foo(self):
            pass
        def _get_vcr_kwargs(self):
            return dict(
                record_mode='new_episodes',
            )
        _get_cassette_library_dir = Mock(return_value='/testing')
    test = run_testcase(MyTest)[0][0]
    assert test.cassette._path.startswith('/testing/')
    assert test._get_cassette_library_dir.call_count == 1

    # Test that _get_cassette_library_dir is ignored if cassette_library_dir
    # is present in vcr kwargs.
    class MyTest(VCRTestCase):
        def test_foo(self):
            pass
        def _get_vcr_kwargs(self):
            return dict(
                cassette_library_dir='/testing',
            )
        _get_cassette_library_dir = Mock(return_value='/ignored')
    test = run_testcase(MyTest)[0][0]
    assert test.cassette._path.startswith('/testing/')
    assert test._get_cassette_library_dir.call_count == 0


def test_get_vcr_with_matcher(tmpdir):
    cassette_dir = tmpdir.mkdir('cassettes')
    assert len(cassette_dir.listdir()) == 0

    mock_matcher = Mock(return_value=True)

    class MyTest(VCRTestCase):
        def test_foo(self):
            self.response = urlopen('http://example.com').read()
        def _get_vcr(self):
            myvcr = super(MyTest, self)._get_vcr()
            myvcr.register_matcher('mymatcher', mock_matcher)
            myvcr.match_on = ['mymatcher']
            return myvcr
        def _get_cassette_library_dir(self):
            return str(cassette_dir)

    # First run to fill cassette.
    test = run_testcase(MyTest)[0][0]
    assert len(test.cassette.requests) == 1
    assert not mock_matcher.called  # nothing in cassette

    # Second run to call matcher.
    test = run_testcase(MyTest)[0][0]
    assert len(test.cassette.requests) == 1
    assert mock_matcher.called
    assert repr(mock_matcher.mock_calls[0]) == 'call(<Request (GET) http://example.com>, <Request (GET) http://example.com>)'


def test_testcase_playback(tmpdir):
    cassette_dir = tmpdir.mkdir('cassettes')
    assert len(cassette_dir.listdir()) == 0

    # First test actually reads from the web.

    class MyTest(VCRTestCase):
        def test_foo(self):
            self.response = urlopen('http://example.com').read()
        def _get_cassette_library_dir(self):
            return str(cassette_dir)

    test = run_testcase(MyTest)[0][0]
    assert b'illustrative examples' in test.response
    assert len(test.cassette.requests) == 1
    assert test.cassette.play_count == 0

    # Second test reads from cassette.

    test2 = run_testcase(MyTest)[0][0]
    assert test.cassette is not test2.cassette
    assert b'illustrative examples' in test.response
    assert len(test2.cassette.requests) == 1
    assert test2.cassette.play_count == 1


def run_testcase(testcase_class):
    """Run all the tests in a TestCase and return them."""
    suite = defaultTestLoader.loadTestsFromTestCase(testcase_class)
    tests = list(suite._tests)
    result = TextTestRunner().run(suite)
    return tests, result
