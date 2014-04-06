import itertools

from vcr import matchers
from vcr import request

# the dict contains requests with corresponding to its key difference
# with 'base' request.
REQUESTS = {
    'base': request.Request('GET', 'http://host.com:80/', '', {}),
    'method': request.Request('POST', 'http://host.com:80/', '', {}),
    'protocol': request.Request('GET', 'https://host.com:80/', '', {}),
    'host': request.Request('GET', 'http://another-host.com:80/', '', {}),
    'port': request.Request('GET', 'http://host.com:90/', '', {}),
    'path': request.Request('GET', 'http://host.com:80/a', '', {}),
    'query': request.Request('GET', 'http://host.com:80/?a=b', '', {}),
}


def assert_matcher(matcher_name):
    matcher = getattr(matchers, matcher_name)
    for k1, k2 in itertools.permutations(REQUESTS, 2):
        matched = matcher(REQUESTS[k1], REQUESTS[k2])
        if matcher_name in {k1, k2}:
            assert not matched
        else:
            assert matched


def test_url_matcher():
    for k1, k2 in itertools.permutations(REQUESTS, 2):
        matched = matchers.url(REQUESTS[k1], REQUESTS[k2])
        if {k1, k2} != {'base', 'method'}:
            assert not matched
        else:
            assert matched


def test_metchers():
    assert_matcher('method')
    assert_matcher('host')
    assert_matcher('port')
    #assert_matcher('method')
