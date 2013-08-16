import urllib2
import vcr

def test_recorded_request_url_with_redirected_request(tmpdir):
    with vcr.use_cassette(str(tmpdir.join('test.yml'))) as cass:
        assert len(cass) == 0
        num_requests = 3
        urllib2.urlopen(
            'https://httpbin.org/redirect/{i}'.format(
                i=num_requests
            )
        )
        for i, j in zip(range(num_requests),range(num_requests, 0, -1)):
            assert cass.requests[i].url == 'https://httpbin.org/redirect/{i}'.format(
                i=j
            )
        assert cass.requests[-1].url == 'https://httpbin.org/get'
        assert len(cass) == num_requests+1
