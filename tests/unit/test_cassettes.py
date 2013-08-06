import yaml
from vcr.cassette import Cassette

def test_cassette_load(tmpdir):
    a_file = tmpdir.join('test_cassette.yml')
    a_file.write(yaml.dumps([
        {'request':'foo', 'response':'bar'}
    ]))
    a_cassette = Cassette.load(a_file)
    assert a_cassette._requests
    assert a_cassette._responses

