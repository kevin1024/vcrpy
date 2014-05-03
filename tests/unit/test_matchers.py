import itertools

from vcr import matchers
from vcr import request

# the dict contains requests with corresponding to its key difference
# with 'base' request.
REQUESTS = {
    'base': request.Request('GET', 'http://host.com/p?a=b', '', {}),
    'method': request.Request('POST', 'http://host.com/p?a=b', '', {}),
    'scheme': request.Request('GET', 'https://host.com:80/p?a=b', '', {}),
    'host': request.Request('GET', 'http://another-host.com/p?a=b', '', {}),
    'port': request.Request('GET', 'http://host.com:90/p?a=b', '', {}),
    'path': request.Request('GET', 'http://host.com/x?a=b', '', {}),
    'query': request.Request('GET', 'http://host.com/p?c=d', '', {}),
}


def assert_matcher(matcher_name):
    matcher = getattr(matchers, matcher_name)
    for k1, k2 in itertools.permutations(REQUESTS, 2):
        matched = matcher(REQUESTS[k1], REQUESTS[k2])
        if matcher_name in set((k1, k2)):
            assert not matched
        else:
            assert matched


def test_uri_matcher():
    for k1, k2 in itertools.permutations(REQUESTS, 2):
        matched = matchers.uri(REQUESTS[k1], REQUESTS[k2])
        if set((k1, k2)) != set(('base', 'method')):
            assert not matched
        else:
            assert matched


def test_query_matcher():
    req1 = request.Request('GET', 'http://host.com/?a=b&c=d', '', {})
    req2 = request.Request('GET', 'http://host.com/?c=d&a=b', '', {})
    assert matchers.query(req1, req2)

    req1 = request.Request('GET', 'http://host.com/?a=b&a=b&c=d', '', {})
    req2 = request.Request('GET', 'http://host.com/?a=b&c=d&a=b', '', {})
    req3 = request.Request('GET', 'http://host.com/?c=d&a=b&a=b', '', {})
    assert matchers.query(req1, req2)
    assert matchers.query(req1, req3)


def test_metchers():
    assert_matcher('method')
    assert_matcher('scheme')
    assert_matcher('host')
    assert_matcher('port')
    assert_matcher('path')
    assert_matcher('query')
