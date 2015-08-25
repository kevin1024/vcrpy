from vcr.filters import (
    remove_headers, replace_headers,
    remove_query_parameters,
    remove_post_data_parameters
)
from vcr.compat import mock
from vcr.request import Request
import json


def test_replace_headers():
    # This tests all of:
    #   1. keeping a header
    #   2. removing a header
    #   3. replacing a header
    #   4. replacing a header using a callable
    #   5. removing a header using a callable
    #   6. replacing a header that doesn't exist
    headers = {
        'one': ['keep'],
        'two': ['lose'],
        'three': ['change'],
        'four': ['shout'],
        'five': ['whisper'],
    }
    request = Request('GET', 'http://google.com', '', headers)
    replace_headers(request, [
        ('two', None),
        ('three', 'tada'),
        ('four', lambda key, value, request: value.upper()),
        ('five', lambda key, value, request: None),
        ('six', 'doesntexist'),
    ])
    assert request.headers == {
        'one': 'keep',
        'three': 'tada',
        'four': 'SHOUT',
    }


def test_replace_headers_empty():
    headers = {'hello': 'goodbye', 'secret': 'header'}
    request = Request('GET', 'http://google.com', '', headers)
    replace_headers(request, [])
    assert request.headers == headers


def test_replace_headers_callable():
    # This goes beyond test_replace_headers() to ensure that the callable
    # receives the expected arguments.
    headers = {'hey': 'there'}
    request = Request('GET', 'http://google.com', '', headers)
    callme = mock.Mock(return_value='ho')
    replace_headers(request, [('hey', callme)])
    assert request.headers == {'hey': 'ho'}
    assert callme.call_args == ((), {'request': request,
                                     'key': 'hey',
                                     'value': 'there'})


def test_remove_headers():
    # Test the backward-compatible API wrapper.
    headers = {'hello': ['goodbye'], 'secret': ['header']}
    request = Request('GET', 'http://google.com', '', headers)
    remove_headers(request, ['secret'])
    assert request.headers == {'hello': 'goodbye'}


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


def test_remove_json_post_data_parameters():
    body = b'{"id": "secret", "foo": "bar", "baz": "qux"}'
    request = Request('POST', 'http://google.com', body, {})
    request.headers['Content-Type'] = 'application/json'
    remove_post_data_parameters(request, ['id'])
    request_body_json = json.loads(request.body.decode('utf-8'))
    expected_json = json.loads(b'{"foo": "bar", "baz": "qux"}'.decode('utf-8'))
    assert request_body_json == expected_json


def test_remove_all_json_post_data_parameters():
    body = b'{"id": "secret", "foo": "bar"}'
    request = Request('POST', 'http://google.com', body, {})
    request.headers['Content-Type'] = 'application/json'
    remove_post_data_parameters(request, ['id', 'foo'])
    assert request.body == b'{}'


def test_remove_nonexistent_json_post_data_parameters():
    body = b'{}'
    request = Request('POST', 'http://google.com', body, {})
    request.headers['Content-Type'] = 'application/json'
    remove_post_data_parameters(request, ['id'])
    assert request.body == b'{}'
