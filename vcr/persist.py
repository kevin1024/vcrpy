from .persisters.filesystem import FilesystemPersister
from .serialize import serialize, deserialize


def load_cassette(cassette_path, serializer):
    with open(cassette_path) as f:
        cassette_content = f.read()
        cassette = deserialize(cassette_content, serializer)
        return cassette


def save_cassette(cassette_path, cassette_dict, serializer):
    data = serialize(cassette_dict, serializer)
    FilesystemPersister.write(cassette_path, data)
