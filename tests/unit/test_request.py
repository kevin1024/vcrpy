from vcr.request import Request


def test_str():
    req = Request('GET', 'http://www.google.com:80/', '', {})
    str(req) == '<Request (GET) http://www.google.com:80/>'


def test_headers():
    headers = {'X-Header1': ['h1'], 'X-Header2': 'h2'}
    req = Request('GET', 'http://go.com:80/', '', headers)
    assert req.headers == {'X-Header1': ['h1'], 'X-Header2': ['h2']}

    req.add_header('X-Header1', 'h11')
    assert req.headers == {'X-Header1': ['h1', 'h11'], 'X-Header2': ['h2']}


def test_flat_headers_dict():
    headers = {'X-Header1': ['h1', 'h11'], 'X-Header2': ['h2']}
    req = Request('GET', 'http://go.com:80/', '', headers)
    assert req.flat_headers_dict() == {'X-Header1': 'h1', 'X-Header2': 'h2'}
