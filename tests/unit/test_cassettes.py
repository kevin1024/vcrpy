import copy

from six.moves import http_client as httplib
import contextlib2
import mock
import pytest
import yaml

from vcr.cassette import Cassette
from vcr.errors import UnhandledHTTPRequestError
from vcr.patch import force_reset
from vcr.stubs import VCRHTTPSConnection



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


def make_get_request():
    conn = httplib.HTTPConnection("www.python.org")
    conn.request("GET", "/index.html")
    return conn.getresponse()


@mock.patch('vcr.cassette.requests_match', return_value=True)
@mock.patch('vcr.cassette.load_cassette', lambda *args, **kwargs: (('foo',), (mock.MagicMock(),)))
@mock.patch('vcr.cassette.Cassette.can_play_response_for', return_value=True)
@mock.patch('vcr.stubs.VCRHTTPResponse')
def test_function_decorated_with_use_cassette_can_be_invoked_multiple_times(*args):
    decorated_function = Cassette.use('test')(make_get_request)
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

    with mock.patch.object(Cassette, 'load', return_value=mock.MagicMock(inject=False)) as cassette_load:
        function()
        cassette_load.assert_called_once_with(arg_getter.return_value[0],
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


def assert_get_response_body_is(value):
    conn = httplib.HTTPConnection("www.python.org")
    conn.request("GET", "/index.html")
    assert conn.getresponse().read().decode('utf8') == value


@mock.patch('vcr.cassette.requests_match', _mock_requests_match)
@mock.patch('vcr.cassette.Cassette.can_play_response_for', return_value=True)
@mock.patch('vcr.cassette.Cassette._save', return_value=True)
def test_nesting_cassette_context_managers(*args):
    first_response = {'body': {'string': b'first_response'}, 'headers': {},
                      'status': {'message': 'm', 'code': 200}}

    second_response = copy.deepcopy(first_response)
    second_response['body']['string'] = b'second_response'

    with contextlib2.ExitStack() as exit_stack:
        first_cassette = exit_stack.enter_context(Cassette.use('test'))
        exit_stack.enter_context(mock.patch.object(first_cassette, 'play_response',
                                                    return_value=first_response))
        assert_get_response_body_is('first_response')

        # Make sure a second cassette can supercede the first
        with Cassette.use('test') as second_cassette:
            with mock.patch.object(second_cassette, 'play_response', return_value=second_response):
                assert_get_response_body_is('second_response')

        # Now the first cassette should be back in effect
        assert_get_response_body_is('first_response')


def test_nesting_context_managers_by_checking_references_of_http_connection():
    original = httplib.HTTPConnection
    with Cassette.use('test'):
        first_cassette_HTTPConnection = httplib.HTTPConnection
        with Cassette.use('test'):
            second_cassette_HTTPConnection = httplib.HTTPConnection
            assert second_cassette_HTTPConnection is not first_cassette_HTTPConnection
            with Cassette.use('test'):
                assert httplib.HTTPConnection is not second_cassette_HTTPConnection
                with force_reset():
                    assert httplib.HTTPConnection is original
            assert httplib.HTTPConnection is second_cassette_HTTPConnection
        assert httplib.HTTPConnection is first_cassette_HTTPConnection


def test_custom_patchers():
    class Test(object):
        attribute = None
    with Cassette.use('custom_patches', custom_patches=((Test, 'attribute', VCRHTTPSConnection),)):
        assert issubclass(Test.attribute, VCRHTTPSConnection)
        assert VCRHTTPSConnection is not Test.attribute
        old_attribute = Test.attribute

        with Cassette.use('custom_patches', custom_patches=((Test, 'attribute', VCRHTTPSConnection),)):
            assert issubclass(Test.attribute, VCRHTTPSConnection)
            assert VCRHTTPSConnection is not Test.attribute
            assert  Test.attribute is not old_attribute

        assert issubclass(Test.attribute, VCRHTTPSConnection)
        assert VCRHTTPSConnection is not Test.attribute
        assert  Test.attribute is old_attribute
