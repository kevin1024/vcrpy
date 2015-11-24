import pytest

from vcr.request import Request, HeadersDict


def test_str():
    req = Request('GET', 'http://www.google.com/', '', {})
    str(req) == '<Request (GET) http://www.google.com/>'


def test_headers():
    headers = {'X-Header1': ['h1'], 'X-Header2': 'h2'}
    req = Request('GET', 'http://go.com/', '', headers)
    assert req.headers == {'X-Header1': 'h1', 'X-Header2': 'h2'}
    req.headers['X-Header1'] = 'h11'
    assert req.headers == {'X-Header1': 'h11', 'X-Header2': 'h2'}


def test_add_header_deprecated():
    req = Request('GET', 'http://go.com/', '', {})
    pytest.deprecated_call(req.add_header, 'foo', 'bar')
    assert req.headers == {'foo': 'bar'}


@pytest.mark.parametrize("uri, expected_port", [
    ('http://go.com/', 80),
    ('http://go.com:80/', 80),
    ('http://go.com:3000/', 3000),
    ('https://go.com/', 443),
    ('https://go.com:443/', 443),
    ('https://go.com:3000/', 3000),
])
def test_port(uri, expected_port):
    req = Request('GET', uri, '', {})
    assert req.port == expected_port


def test_uri():
    req = Request('GET', 'http://go.com/', '', {})
    assert req.uri == 'http://go.com/'

    req = Request('GET', 'http://go.com:80/', '', {})
    assert req.uri == 'http://go.com:80/'


def test_HeadersDict():

    # Simple test of CaseInsensitiveDict
    h = HeadersDict()
    assert h == {}
    h['Content-Type'] = 'application/json'
    assert h == {'Content-Type': 'application/json'}
    assert h['content-type'] == 'application/json'
    assert h['CONTENT-TYPE'] == 'application/json'

    # Test feature of HeadersDict: devolve list to first element
    h = HeadersDict()
    assert h == {}
    h['x'] = ['foo', 'bar']
    assert h == {'x': 'foo'}

    # Test feature of HeadersDict: preserve original key case
    h = HeadersDict()
    assert h == {}
    h['Content-Type'] = 'application/json'
    assert h == {'Content-Type': 'application/json'}
    h['content-type'] = 'text/plain'
    assert h == {'Content-Type': 'text/plain'}
    h['CONtent-tyPE'] = 'whoa'
    assert h == {'Content-Type': 'whoa'}
