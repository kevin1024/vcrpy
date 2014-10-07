import mock
import pytest

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


@mock.patch.object(jsonserializer.json, 'dumps',
                   side_effect=UnicodeDecodeError('utf-8', b'unicode error in serialization',
                                                  0, 10, 'blew up'))
def test_serialize_constructs_UnicodeDecodeError(mock_dumps):
    with pytest.raises(UnicodeDecodeError):
        jsonserializer.serialize({})
