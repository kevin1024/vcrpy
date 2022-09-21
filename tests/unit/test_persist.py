import pytest

from vcr.persisters.filesystem import FilesystemPersister
from vcr.serializers import jsonserializer, yamlserializer

from ..fixtures import migration
import importlib_resources

migration_fixtures = importlib_resources.files(migration)

@pytest.mark.parametrize(
    "cassette_path, serializer",
    [
        ("old_cassette.json", jsonserializer),
        ("old_cassette.yaml", yamlserializer),
    ],
)
def test_load_cassette_with_old_cassettes(cassette_path, serializer):
    with pytest.raises(ValueError) as excinfo:
        FilesystemPersister.load_cassette(migration_fixtures / cassette_path, serializer)
    assert "run the migration script" in excinfo.exconly()


@pytest.mark.parametrize(
    "cassette_path, serializer",
    [
        ("not_cassette.txt", jsonserializer),
        ("not_cassette.txt", yamlserializer),
    ],
)
def test_load_cassette_with_invalid_cassettes(cassette_path, serializer):
    with pytest.raises(Exception) as excinfo:
        FilesystemPersister.load_cassette(migration_fixtures / cassette_path, serializer)
    assert "run the migration script" not in excinfo.exconly()
