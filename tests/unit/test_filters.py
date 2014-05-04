from vcr.filters import _remove_headers, _remove_query_parameters
from vcr.request import Request


def test_remove_headers():
    headers = {'hello': ['goodbye'], 'secret': ['header']}
    request = Request('GET', 'http://google.com', '', headers)
    _remove_headers(request, ['secret'])
    assert request.headers == {'hello': 'goodbye'}


def test_remove_headers_empty():
    headers = {'hello': 'goodbye', 'secret': 'header'}
    request = Request('GET', 'http://google.com', '', headers)
    _remove_headers(request, [])
    assert request.headers == headers


def test_remove_query_parameters():
    uri = 'http://g.com/?q=cowboys&w=1'
    request = Request('GET', uri, '', {})
    _remove_query_parameters(request, ['w'])
    assert request.uri == 'http://g.com/?q=cowboys'


def test_remove_all_query_parameters():
    uri = 'http://g.com/?q=cowboys&w=1'
    request = Request('GET', uri, '', {})
    _remove_query_parameters(request, ['w', 'q'])
    assert request.uri == 'http://g.com/'


def test_remove_nonexistent_query_parameters():
    uri = 'http://g.com/'
    request = Request('GET', uri, '', {})
    _remove_query_parameters(request, ['w', 'q'])
    assert request.uri == 'http://g.com/'
