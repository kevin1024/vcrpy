from six.moves import http_client as httplib

import pytest
import yaml
import mock

from vcr.cassette import Cassette
from vcr.errors import UnhandledHTTPRequestError


def test_cassette_load(tmpdir):
    a_file = tmpdir.join('test_cassette.yml')
    a_file.write(yaml.dump({'interactions': [
        {'request': {'body': '', 'uri': 'foo', 'method': 'GET', 'headers': {}},
         'response': 'bar'}
    ]}))
    a_cassette = Cassette.load(str(a_file))
    assert len(a_cassette) == 1


def test_cassette_not_played():
    a = Cassette('test')
    assert not a.play_count


def test_cassette_append():
    a = Cassette('test')
    a.append('foo', 'bar')
    assert a.requests == ['foo']
    assert a.responses == ['bar']


def test_cassette_len():
    a = Cassette('test')
    a.append('foo', 'bar')
    a.append('foo2', 'bar2')
    assert len(a) == 2


def _mock_requests_match(request1, request2, matchers):
    return request1 == request2


@mock.patch('vcr.cassette.requests_match', _mock_requests_match)
def test_cassette_contains():
    a = Cassette('test')
    a.append('foo', 'bar')
    assert 'foo' in a


@mock.patch('vcr.cassette.requests_match', _mock_requests_match)
def test_cassette_responses_of():
    a = Cassette('test')
    a.append('foo', 'bar')
    assert a.responses_of('foo') == ['bar']


@mock.patch('vcr.cassette.requests_match', _mock_requests_match)
def test_cassette_get_missing_response():
    a = Cassette('test')
    with pytest.raises(UnhandledHTTPRequestError):
        a.responses_of('foo')


@mock.patch('vcr.cassette.requests_match', _mock_requests_match)
def test_cassette_cant_read_same_request_twice():
    a = Cassette('test')
    a.append('foo', 'bar')
    a.play_response('foo')
    with pytest.raises(UnhandledHTTPRequestError):
        a.play_response('foo')


@mock.patch('vcr.cassette.requests_match', return_value=True)
@mock.patch('vcr.cassette.load_cassette', lambda *args, **kwargs: (('foo',), (mock.MagicMock(),)))
@mock.patch('vcr.cassette.Cassette.can_play_response_for', return_value=True)
@mock.patch('vcr.stubs.VCRHTTPResponse')
def test_function_decorated_with_use_cassette_can_be_invoked_multiple_times(*args):
    @Cassette.use('test')
    def decorated_function():
        conn = httplib.HTTPConnection("www.python.org")
        conn.request("GET", "/index.html")
        conn.getresponse()

    for i in range(2):
         decorated_function()


def test_arg_getter_functionality():
    arg_getter = mock.Mock(return_value=('test', {}))
    context_decorator = Cassette.use_arg_getter(arg_getter)

    with context_decorator as cassette:
        assert cassette._path == 'test'

    arg_getter.return_value = ('other', {})

    with context_decorator as cassette:
        assert cassette._path == 'other'

    arg_getter.return_value = ('', {'filter_headers': ('header_name',)})

    @context_decorator
    def function():
        pass

    with mock.patch.object(Cassette, '__init__', return_value=None) as cassette_init, \
         mock.patch.object(Cassette, '_load'), \
         mock.patch.object(Cassette, '__exit__'):
        function()
        cassette_init.assert_called_once_with(arg_getter.return_value[0],
                                              **arg_getter.return_value[1])


def test_cassette_not_all_played():
    a = Cassette('test')
    a.append('foo', 'bar')
    assert not a.all_played


@mock.patch('vcr.cassette.requests_match', _mock_requests_match)
def test_cassette_all_played():
    a = Cassette('test')
    a.append('foo', 'bar')
    a.play_response('foo')
    assert a.all_played


def test_before_record_response():
    before_record_response = mock.Mock(return_value='mutated')
    cassette = Cassette('test', before_record_response=before_record_response)
    cassette.append('req', 'res')

    before_record_response.assert_called_once_with('res')
    assert cassette.responses[0] == 'mutated'
