import pytest

from vcr.persisters.filesystem import FilesystemPersister
from vcr.serializers import jsonserializer, yamlserializer


@pytest.mark.parametrize(
    "cassette_path, serializer, expected_message",
    [
        # Old JSON cassettes are recognized as old-format and pointed at the
        # migration script.
        ("tests/fixtures/migration/old_cassette.json", jsonserializer, "run the migration script"),
        # Old YAML cassettes contain python object tags the safe loader
        # refuses, so they surface the unsupported-tag error instead.
        ("tests/fixtures/migration/old_cassette.yaml", yamlserializer, "problem loading the cassette"),
    ],
)
def test_load_cassette_with_old_cassettes(cassette_path, serializer, expected_message):
    with pytest.raises(ValueError) as excinfo:
        FilesystemPersister.load_cassette(cassette_path, serializer)
    assert expected_message in excinfo.exconly()


@pytest.mark.parametrize(
    "cassette_path, serializer",
    [
        ("tests/fixtures/migration/not_cassette.txt", jsonserializer),
        ("tests/fixtures/migration/not_cassette.txt", yamlserializer),
    ],
)
def test_load_cassette_with_invalid_cassettes(cassette_path, serializer):
    with pytest.raises(Exception) as excinfo:
        FilesystemPersister.load_cassette(cassette_path, serializer)
    assert "run the migration script" not in excinfo.exconly()
