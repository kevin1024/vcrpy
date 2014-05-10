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
