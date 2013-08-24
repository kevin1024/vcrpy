from .persisters.filesystem import FilesystemPersister


def load_cassette(cassette_path, serializer):
    with open(cassette_path) as f:
        return serializer.deserialize(f.read())


def save_cassette(cassette_path, cassette_dict, serializer):
    data = serializer.serialize(cassette_dict)
    FilesystemPersister.write(cassette_path, data)
