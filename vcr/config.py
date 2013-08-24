import os
from .cassette import Cassette
from .serializers import yamlserializer, jsonserializer


class VCR(object):
    def __init__(self, serializer='yaml', cassette_library_dir=None):
        self.serializer = serializer
        self.cassette_library_dir = cassette_library_dir
        self.serializers = {
            'yaml': yamlserializer,
            'json': jsonserializer,
        }

    def _get_serializer(self, serializer_name):
        try:
            serializer = self.serializers[serializer_name]
        except KeyError:
            print "Serializer {0} doesn't exist or isn't registered".format(
                serializer_name
            )
            raise KeyError
        return serializer

    def use_cassette(self, path, **kwargs):
        serializer_name = kwargs.get('serializer', self.serializer)
        cassette_library_dir = kwargs.get(
            'cassette_library_dir',
            self.cassette_library_dir
        )

        if cassette_library_dir:
            path = os.path.join(cassette_library_dir, path)

        merged_config = {
            "serializer": self._get_serializer(serializer_name),
        }

        return Cassette.load(path, **merged_config)

    def register_serializer(self, name, serializer):
        self.serializers[name] = serializer
