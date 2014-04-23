import pytest

import vcr.persist
from vcr.serializers import jsonserializer, yamlserializer


@pytest.mark.parametrize("cassette_path, serializer", [
    ('tests/fixtures/migration/old_cassette.json', jsonserializer),
    ('tests/fixtures/migration/old_cassette.yaml', yamlserializer),
])
def test_load_cassette_with_old_cassettes(cassette_path, serializer):
    with pytest.raises(ValueError) as excinfo:
        vcr.persist.load_cassette(cassette_path, serializer)
    assert "run the migration script" in excinfo.exconly()
