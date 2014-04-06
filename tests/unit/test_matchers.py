from vcr import matchers
from vcr import request


def test_method():
    req_get = request.Request('GET', 'http://google.com:80/', '', {})
    assert True == matchers.method(req_get, req_get)

    req_get1 = request.Request('GET', 'https://httpbin.org:80/', '', {})
    assert True == matchers.method(req_get, req_get1)

    req_post = request.Request('POST', 'http://google.com:80/', '', {})
    assert False == matchers.method(req_get, req_post)


def test_url():
    req1 = request.Request('GET', 'http://google.com:80/', '', {})
    assert True == matchers.url(req1, req1)

    req2 = request.Request('GET', 'https://httpbin.org:80/', '', {})
    assert False == matchers.url(req1, req2)

    req1_post = request.Request('POST', 'http://google.com:80/', '', {})
    assert True == matchers.url(req1, req1_post)

    req_query_string = request.Request(
        'GET', 'http://google.com:80/?p1=t1&p2=t2', '', {})
    req_query_string1 = request.Request(
        'GET', 'http://google.com:80/?p2=t2&p1=t1', '', {})
    assert False == matchers.url(req_query_string, req_query_string1)
