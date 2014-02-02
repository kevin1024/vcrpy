import vcr
from vcr._compat import urlopen


def test_recorded_request_url_with_redirected_request(tmpdir):
    with vcr.use_cassette(str(tmpdir.join('test.yml'))) as cass:
        assert len(cass) == 0
        urlopen('http://httpbin.org/redirect/3')
        assert cass.requests[0].url == 'http://httpbin.org/redirect/3'
        assert cass.requests[3].url == 'http://httpbin.org/get'
        assert len(cass) == 4
