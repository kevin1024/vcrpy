import mock
from vcr.filters import _remove_headers, _remove_query_parameters
from vcr.request import Request


def test_remove_headers():
    request = mock.Mock(headers=[('hello','goodbye'),('secret','header')])
    assert _remove_headers(request, ['secret']).headers == frozenset([('hello','goodbye')])


def test_remove_headers_empty():
    request = mock.Mock(headers=[('hello','goodbye'),('secret','header')])
    assert _remove_headers(request, []).headers == frozenset([('hello','goodbye'),('secret','header')])


def test_remove_query_parameters():
    request = mock.Mock(url='http://g.com/?q=cowboys&w=1')
    assert _remove_query_parameters(request, ['w']).path == '/?q=cowboys'


def test_remove_all_query_parameters():
    request = mock.Mock(url='http://g.com/?q=cowboys&w=1')
    assert _remove_query_parameters(request, ['w','q']).path == '/'


def test_remove_nonexistent_query_parameters():
    request = mock.Mock(url='http://g.com/')
    assert _remove_query_parameters(request, ['w','q']).path == '/'
