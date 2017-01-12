from .persisters.filesystem import FilesystemPersister
from .serialize import serialize, deserialize


def load_cassette(cassette_path, serializer, load_callback=None):
    # Injected `load_callback` must return a cassette or raise IOError
    if load_callback is None:
        with open(cassette_path) as f:
            cassette_content = f.read()
    else:
        cassette_content = load_callback(cassette_path)
    cassette = deserialize(cassette_content, serializer)
    return cassette


def save_cassette(
        cassette_path,
        cassette_dict,
        serializer,
        save_callback=None
):
    data = serialize(cassette_dict, serializer)
    if save_callback is None:
        FilesystemPersister.write(cassette_path, data)
    else:
        save_callback(cassette_path, data)
