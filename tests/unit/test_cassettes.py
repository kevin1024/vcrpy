import mock
import yaml
from vcr.cassette import Cassette

def test_cassette_load(tmpdir):
    a_file = tmpdir.join('test_cassette.yml')
    a_file.write(yaml.dump([
        {'request':'foo', 'response':'bar'}
    ]))
    a_cassette = Cassette.load(str(a_file))
    assert a_cassette._requests
    assert a_cassette._responses

def test_cassette_serialize():
    a = Cassette('test')
    a._requests = ['foo']
    a._responses = ['bar']
    assert a.serialize() == [{'request': 'foo', 'response': 'bar'}]

def test_cassette_deserialize():
    a = Cassette('test')
    a.deserialize([{'request': 'foo', 'response': 'bar'}])
    assert a._requests == ['foo']
    assert a._responses == ['bar']

def test_cassette_not_played():
    a = Cassette('test')
    assert not a.play_count

def test_cassette_played():
    a = Cassette('test')
    a.mark_played()
    assert a.play_count == 1

def test_cassette_append():
    a = Cassette('test')
    a.append('foo', 'bar')
    assert a._requests == ['foo']
    assert a._responses == ['bar']

def test_cassette_len():
    a = Cassette('test')
    a.append('foo','bar')
    a.append('foo2','bar2')
    assert len(a) == 2

def test_cassette_contains():
    a = Cassette('test')
    a.append('foo','bar')
    assert 'foo' in a

def test_cassette_response():
    a = Cassette('test')
    a.append('foo','bar')
    assert a.response('foo') == 'bar'

def test_cassette_missing_response():
    a = Cassette('test')
    assert not a.response('foo')
