import urllib2
import vcr

def test_recorded_request_url_with_redirected_request(tmpdir):
    with vcr.use_cassette(str(tmpdir.join('test.yml'))) as cass:
        assert len(cass) == 0
        urllib2.urlopen('http://google.com')
        print cass.requests
        print cass.requests[0]
        assert cass.requests[0].url == 'http://google.com'
        assert cass.requests[1].url == 'http://www.google.com/'
        assert len(cass) == 2
