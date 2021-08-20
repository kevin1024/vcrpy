import pytest
from unittest.mock import patch

from vcr.persisters.filesystem import FilesystemPersister
from vcr.persisters.deduplicated_filesystem import DeduplicatedFilesystemPersister
from vcr.serializers import jsonserializer, yamlserializer
import vcr

@pytest.mark.parametrize(
    "cassette_path, serializer",
    [
        ("tests/fixtures/migration/old_cassette.json", jsonserializer),
        ("tests/fixtures/migration/old_cassette.yaml", yamlserializer),
    ],
)
def test_load_cassette_with_old_cassettes(cassette_path, serializer):
    with pytest.raises(ValueError) as excinfo:
        FilesystemPersister.load_cassette(cassette_path, serializer)
    assert "run the migration script" in excinfo.exconly()


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

@pytest.mark.parametrize(
    "cassette_path, serializer",
    [
        ("tests/fixtures/migration/cassette_with_duplicate_requests.yaml", yamlserializer),
    ],
)
def test_load_cassette_with_duplicate_requests_cassettes(cassette_path, serializer):
    cassette_dict = DeduplicatedFilesystemPersister.load_cassette(cassette_path, serializer)
    breakpoint()
    with patch.object(FilesystemPersister, "save_cassette") as mock:
        with vcr.use_cassette(cassette_path, serializer=serializer, persister=DeduplicatedFilesystemPersister):
            pass

        # it's deduped when it is saved
        # DeduplicatedFilesystemPersister.save_cassette(cassette_path, cassette_dict, serializer)
        breakpoint()
        assert mock.call_count == 1

