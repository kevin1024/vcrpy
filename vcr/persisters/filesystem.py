# .. _persister_example:

import os

from ..serialize import deserialize, serialize


class FilesystemPersister:
    @classmethod
    def load_cassette(cls, cassette_path, serializer):
        try:
            with open(cassette_path, encoding="utf-8") as f:
                cassette_content = f.read()
        except OSError:
            raise ValueError("Cassette not found.")
        cassette = deserialize(cassette_content, serializer)
        return cassette

    @staticmethod
    def save_cassette(cassette_path, cassette_dict, serializer):
        data = serialize(cassette_dict, serializer)
        dirname, filename = os.path.split(cassette_path)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname)
        with open(cassette_path, "w", encoding="utf-8") as f:
            f.write(data)
