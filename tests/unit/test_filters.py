from vcr.filters import (
    remove_headers,
    remove_query_parameters,
    remove_post_data_parameters
)
from vcr.request import Request


def test_remove_headers():
    headers = {'hello': ['goodbye'], 'secret': ['header']}
    request = Request('GET', 'http://google.com', '', headers)
    remove_headers(request, ['secret'])
    assert request.headers == {'hello': 'goodbye'}


def test_remove_headers_empty():
    headers = {'hello': 'goodbye', 'secret': 'header'}
    request = Request('GET', 'http://google.com', '', headers)
    remove_headers(request, [])
    assert request.headers == headers


def test_remove_query_parameters():
    uri = 'http://g.com/?q=cowboys&w=1'
    request = Request('GET', uri, '', {})
    remove_query_parameters(request, ['w'])
    assert request.uri == 'http://g.com/?q=cowboys'


def test_remove_all_query_parameters():
    uri = 'http://g.com/?q=cowboys&w=1'
    request = Request('GET', uri, '', {})
    remove_query_parameters(request, ['w', 'q'])
    assert request.uri == 'http://g.com/'


def test_remove_nonexistent_query_parameters():
    uri = 'http://g.com/'
    request = Request('GET', uri, '', {})
    remove_query_parameters(request, ['w', 'q'])
    assert request.uri == 'http://g.com/'


def test_remove_post_data_parameters():
    body = b'id=secret&foo=bar'
    request = Request('POST', 'http://google.com', body, {})
    remove_post_data_parameters(request, ['id'])
    assert request.body == b'foo=bar'


def test_preserve_multiple_post_data_parameters():
    body = b'id=secret&foo=bar&foo=baz'
    request = Request('POST', 'http://google.com', body, {})
    remove_post_data_parameters(request, ['id'])
    assert request.body == b'foo=bar&foo=baz'


def test_remove_all_post_data_parameters():
    body = b'id=secret&foo=bar'
    request = Request('POST', 'http://google.com', body, {})
    remove_post_data_parameters(request, ['id', 'foo'])
    assert request.body == b''


def test_remove_nonexistent_post_data_parameters():
    body = b''
    request = Request('POST', 'http://google.com', body, {})
    remove_post_data_parameters(request, ['id'])
    assert request.body == b''
