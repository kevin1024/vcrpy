import tempfile

from .persisters.filesystem import FilesystemPersister
from . import migration
from . import serialize


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
            cassette = serialize.deserialize(cassette_content, serializer)
        except TypeError:
            _check_for_old_cassette(cassette_content)
            raise
        return cassette


def save_cassette(cassette_path, cassette_dict, serializer):
    data = serialize.serialize(cassette_dict, serializer)
    FilesystemPersister.write(cassette_path, data)
