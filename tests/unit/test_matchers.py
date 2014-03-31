from vcr import matchers
from vcr import request


def test_method():
    req_get = request.Request('http', 'google.com', 80, 'GET', '/', '', {})
    assert True == matchers.method(req_get, req_get)

    req_get1 = request.Request('https', 'httpbin.org', 80, 'GET', '/', '', {})
    assert True == matchers.method(req_get, req_get1)

    req_post = request.Request('http', 'google.com', 80, 'POST', '/', '', {})
    assert False == matchers.method(req_get, req_post)
