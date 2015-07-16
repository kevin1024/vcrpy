import pytest

from vcr.compat import mock
from vcr.serialize import deserialize
from vcr.serializers import yamlserializer, jsonserializer


def test_deserialize_old_yaml_cassette():
    with open('tests/fixtures/migration/old_cassette.yaml', 'r') as f:
        with pytest.raises(ValueError):
            deserialize(f.read(), yamlserializer)


def test_deserialize_old_json_cassette():
    with open('tests/fixtures/migration/old_cassette.json', 'r') as f:
        with pytest.raises(ValueError):
            deserialize(f.read(), jsonserializer)


def test_deserialize_new_yaml_cassette():
    with open('tests/fixtures/migration/new_cassette.yaml', 'r') as f:
        deserialize(f.read(), yamlserializer)


def test_deserialize_new_json_cassette():
    with open('tests/fixtures/migration/new_cassette.json', 'r') as f:
        deserialize(f.read(), jsonserializer)


def test_deserialize_py2_yaml_cassette():
    # A cassette generated under Python 2 stores the body as a string, but
    # the same cassette generated under Python 3 stores it as "!!binary".
    # Make sure we accept the Python 2 cassette, regardless of whether
    # we're running under Python 2 or 3.
    with open('tests/fixtures/py2body_cassette.yaml') as f:
        (requests, responses) = deserialize(f.read(), yamlserializer)
    assert requests[0].body == b'x=5&y=2'

def test_deserialize_py3_yaml_cassette():
    # Same as previous test, except make sure a cassette written under
    # Python 3 works under both 2 and 3.
    with open('tests/fixtures/py3body_cassette.yaml') as f:
        (requests, responses) = deserialize(f.read(), yamlserializer)
    assert requests[0].body == b'x=5&y=2'

@mock.patch.object(jsonserializer.json, 'dumps',
                   side_effect=UnicodeDecodeError('utf-8', b'unicode error in serialization',
                                                  0, 10, 'blew up'))
def test_serialize_constructs_UnicodeDecodeError(mock_dumps):
    with pytest.raises(UnicodeDecodeError):
        jsonserializer.serialize({})
