import pytest

from vcr.request import Request


def test_str():
    req = Request('GET', 'http://www.google.com/', '', {})
    str(req) == '<Request (GET) http://www.google.com/>'


def test_headers():
    headers = {'X-Header1': ['h1'], 'X-Header2': 'h2'}
    req = Request('GET', 'http://go.com/', '', headers)
    assert req.headers == {'X-Header1': 'h1', 'X-Header2': 'h2'}

    req.add_header('X-Header1', 'h11')
    assert req.headers == {'X-Header1': 'h11', 'X-Header2': 'h2'}


@pytest.mark.parametrize("uri, expected_port", [
    ('http://go.com/', 80),
    ('http://go.com:80/', 80),
    ('http://go.com:3000/', 3000),
    ('https://go.com/', 443),
    ('https://go.com:443/', 443),
    ('https://go.com:3000/', 3000),
    ])
def test_port(uri, expected_port):
    req = Request('GET', uri,  '', {})
    assert req.port == expected_port


def test_uri():
    req = Request('GET', 'http://go.com/', '', {})
    assert req.uri == 'http://go.com/'

    req = Request('GET', 'http://go.com:80/', '', {})
    assert req.uri == 'http://go.com:80/'
