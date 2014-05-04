import tempfile

from .persisters.filesystem import FilesystemPersister
from . import migration


def _check_for_old_cassette(cassette_content):
    # crate tmp with cassete content and try to migrate it
    with tempfile.NamedTemporaryFile(mode='w+') as f:
        f.write(cassette_content)
        f.seek(0)
        if migration.try_migrate(f.name):
            raise ValueError(
                "Your cassette files were generated in an older version "
                "of VCR. Delete your cassettes or run the migration script."
                "See http://git.io/mHhLBg for more details."
            )


def load_cassette(cassette_path, serializer):
    with open(cassette_path) as f:
        cassette_content = f.read()
        try:
            cassette = serializer.deserialize(cassette_content)
        except TypeError:
            _check_for_old_cassette(cassette_content)
            raise
        return cassette


def save_cassette(cassette_path, cassette_dict, serializer):
    data = serializer.serialize(cassette_dict)
    FilesystemPersister.write(cassette_path, data)
