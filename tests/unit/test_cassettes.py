import pytest
import yaml
from vcr.cassette import Cassette

def test_cassette_load(tmpdir):
    a_file = tmpdir.join('test_cassette.yml')
    a_file.write(yaml.dump([
        {'request':'foo', 'response':'bar'}
    ]))
    a_cassette = Cassette.load(str(a_file))
    assert len(a_cassette) == 1

def test_cassette_serialize():
    a = Cassette('test')
    a.append('foo','bar')
    assert a.serialize() == [{'request': 'foo', 'response': 'bar'}]

def test_cassette_deserialize():
    a = Cassette('test')
    a.deserialize([{'request': 'foo', 'response': 'bar'}])
    assert a.requests == {'foo':'bar'}

def test_cassette_not_played():
    a = Cassette('test')
    assert not a.play_count

def test_cassette_played():
    a = Cassette('test')
    a.mark_played('foo')
    a.mark_played('foo')
    assert a.play_count == 2

def test_cassette_play_counter():
    a = Cassette('test')
    a.mark_played('foo')
    a.mark_played('bar')
    assert a.play_counts['foo'] == 1
    assert a.play_counts['bar'] == 1

def test_cassette_append():
    a = Cassette('test')
    a.append('foo', 'bar')
    assert a.requests == {'foo':'bar'}

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
    with pytest.raises(KeyError):
        a.response('foo')
