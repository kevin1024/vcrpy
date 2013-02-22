import json

def assert_httpbin_responses_equal(body1, body2):
    """
    httpbin.org returns a different `origin` header 
    each time, so strip this out since it makes testing
    difficult.
    """
    body1, body2 = json.loads(body1), json.loads(body2)
    del body1['origin']
    del body2['origin']
    assert body1 == body2

