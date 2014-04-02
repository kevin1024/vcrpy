"""
This file contains tests for matchers.

Matcher should return `True` or `False` because of this here used assertions
like 'assert True == matcher()' and not 'assert matcher()'
"""

from vcr import matchers
from vcr import request


def test_method():
    req_get = request.Request('http', 'google.com', 80, 'GET', '/', '', {})
    assert True == matchers.method(req_get, req_get)

    req_get1 = request.Request('https', 'httpbin.org', 80, 'GET', '/', '', {})
    assert True == matchers.method(req_get, req_get1)

    req_post = request.Request('http', 'google.com', 80, 'POST', '/', '', {})
    assert False == matchers.method(req_get, req_post)


def test_url():
    req1 = request.Request('http', 'google.com', 80, 'GET', '/', '', {})
    assert True == matchers.url(req1, req1)

    req2 = request.Request('http', 'httpbin.org', 80, 'GET', '/', '', {})
    assert False == matchers.url(req1, req2)

    req1_post = request.Request('http', 'google.com', 80, 'POST', '/', '', {})
    assert True == matchers.url(req1, req1_post)

    req_query_string = request.Request(
        'http', 'google.com?p1=t1&p2=t2', 80, 'GET', '/', '', {})
    req_query_string1 = request.Request(
        'http', 'google.com?p2=t2&p1=t1', 80, 'GET', '/', '', {})
    assert False == matchers.url(req_query_string, req_query_string1)


def test_semantic_url():
    req0 = request.Request(
        'http', 'httpbin.org', 80, 'GET', '/a', '', {})
    assert True == matchers.semantic_url(req0, req0)

    req1 = request.Request(
        'http', 'httpbin.org', 80, 'GET', '/a?p1=v1&p2=v2', '', {})
    assert True == matchers.semantic_url(req1, req1)

    req2 = request.Request(
        'http', 'httpbin.org', 80, 'GET', '/a?p2=v2&p1=v1', '', {})
    assert True == matchers.semantic_url(req1, req2)

    req3 = request.Request(
        'http', 'httpbin.org', 80, 'GET', '/a?p1=v1&p2=v2&p1=v1', '', {})
    assert False == matchers.semantic_url(req1, req3)
    assert False == matchers.semantic_url(req2, req3)
