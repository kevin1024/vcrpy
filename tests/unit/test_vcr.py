import mock

from vcr import VCR


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
