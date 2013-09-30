import os
from .cassette import Cassette
from .serializers import yamlserializer, jsonserializer
from .matchers import method, url, host, path, headers, body


class VCR(object):
    def __init__(self,
                 serializer='yaml',
                 cassette_library_dir=None,
                 record_mode="once",
                 match_on=['url', 'method'],
                 ):
        self.serializer = serializer
        self.match_on = match_on
        self.cassette_library_dir = cassette_library_dir
        self.serializers = {
            'yaml': yamlserializer,
            'json': jsonserializer,
        }
        self.matchers = {
            'method': method,
            'url': url,
            'host': host,
            'path': path,
            'headers': headers,
            'body': body,
        }
        self.record_mode = record_mode

    def _get_serializer(self, serializer_name):
        try:
            serializer = self.serializers[serializer_name]
        except KeyError:
            print "Serializer {0} doesn't exist or isn't registered".format(
                serializer_name
            )
            raise KeyError
        return serializer

    def _get_matchers(self, matcher_names):
        try:
            matchers = [self.matchers[m] for m in matcher_names]
        except KeyError:
            raise KeyError(
                "Matcher {0} doesn't exist or isn't registered".format(m)
            )
        return matchers

    def use_cassette(self, path, **kwargs):
        serializer_name = kwargs.get('serializer', self.serializer)
        matcher_names = kwargs.get('match_on', self.match_on)
        cassette_library_dir = kwargs.get(
            'cassette_library_dir',
            self.cassette_library_dir
        )

        if cassette_library_dir:
            path = os.path.join(cassette_library_dir, path)

        merged_config = {
            "serializer": self._get_serializer(serializer_name),
            "match_on": self._get_matchers(matcher_names),
            "record_mode": kwargs.get('record_mode', self.record_mode),
        }

        return Cassette.load(path, **merged_config)

    def register_serializer(self, name, serializer):
        self.serializers[name] = serializer

    def register_matcher(self, name, matcher):
        self.matchers[name] = matcher
