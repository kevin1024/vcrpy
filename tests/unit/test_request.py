from vcr.request import Request


def test_url():
    req = Request('http', 'www.google.com', 80, 'GET', '/', '', {})
    assert req.url == 'http://www.google.com/'


def test_str():
    req = Request('http', 'www.google.com', 80, 'GET', '/', '', {})
    str(req) == '<Request (GET) http://www.google.com>'
