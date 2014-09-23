import mock
import pytest

from vcr import VCR, use_cassette


def test_vcr_use_cassette():
    filter_headers = mock.Mock()
    test_vcr = VCR(filter_headers=filter_headers)
    with mock.patch('vcr.cassette.Cassette.load') as mock_cassette_load:
        @test_vcr.use_cassette('test')
        def function():
            pass
        assert mock_cassette_load.call_count == 0
        function()
        assert mock_cassette_load.call_args[1]['filter_headers'] is filter_headers

        # Make sure that calls to function now use cassettes with the
        # new filter_header_settings
        test_vcr.filter_headers = ('a',)
        function()
        assert mock_cassette_load.call_args[1]['filter_headers'] == test_vcr.filter_headers

        # Ensure that explicitly provided arguments still supercede
        # those on the vcr.
        new_filter_headers = mock.Mock()

    with test_vcr.use_cassette('test', filter_headers=new_filter_headers) as cassette:
        assert cassette._filter_headers == new_filter_headers


@pytest.fixture
def random_fixture():
    return 1


@use_cassette('test')
def test_fixtures_with_use_cassette(random_fixture):
    # Applying a decorator to a test function that requests features can cause
    # problems if the decorator does not preserve the signature of the original
    # test function.

    # This test ensures that use_cassette preserves the signature of the original
    # test function, and thus that use_cassette is compatible with py.test
    # fixtures. It is admittedly a bit strange because the test would never even
    # run if the relevant feature were broken.
    pass
