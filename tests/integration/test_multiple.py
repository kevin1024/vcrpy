import pytest
import vcr
from vcr._compat import urlopen


def test_making_extra_request_raises_exception(tmpdir):
    # make two requests in the first request that are considered
    # identical (since the match is based on method)
    with vcr.use_cassette(str(tmpdir.join('test.json')), match_on=['method']):
        urlopen('http://httpbin.org/status/200')
        urlopen('http://httpbin.org/status/201')

    # Now, try to make three requests.  The first two should return the
    # correct status codes in order, and the third should raise an
    # exception.
    with vcr.use_cassette(str(tmpdir.join('test.json')), match_on=['method']):
        assert urlopen('http://httpbin.org/status/200').getcode() == 200
        assert urlopen('http://httpbin.org/status/201').getcode() == 201
        with pytest.raises(Exception):
            urlopen('http://httpbin.org/status/200')
