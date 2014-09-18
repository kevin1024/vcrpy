import mock

from vcr import VCR



def test_vcr_use_cassette():
    filter_headers = mock.Mock()
    test_vcr = VCR(filter_headers=filter_headers)
    with mock.patch('vcr.config.Cassette') as mock_cassette_class:
        @test_vcr.use_cassette('test')
        def function():
            pass
        mock_cassette_class.call_count == 0
        function()
    assert mock_cassette_class.use.call_args[1]['filter_headers'] is filter_headers
