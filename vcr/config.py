import os
from .cassette import Cassette
from .serializers import yamlserializer, jsonserializer
from . import matchers


class VCR(object):
    def __init__(self,
                 serializer='yaml',
                 cassette_library_dir=None,
                 record_mode="once",
                 filter_headers=[],
                 filter_query_parameters=[],
                 before_record=None,
                 match_on=[
                     'method',
                     'scheme',
                     'host',
                     'port',
                     'path',
                     'query',
                 ],
                 ignore_hosts=[],
                 ignore_localhost=False,
                 ):
        self.serializer = serializer
        self.match_on = match_on
        self.cassette_library_dir = cassette_library_dir
        self.serializers = {
            'yaml': yamlserializer,
            'json': jsonserializer,
        }
        self.matchers = {
            'method': matchers.method,
            'uri': matchers.uri,
            'url': matchers.uri,  # matcher for backwards compatibility
            'scheme': matchers.scheme,
            'host': matchers.host,
            'port': matchers.port,
            'path': matchers.path,
            'query': matchers.query,
            'headers': matchers.headers,
            'body': matchers.body,
        }
        self.record_mode = record_mode
        self.filter_headers = filter_headers
        self.filter_query_parameters = filter_query_parameters
        self.before_record = before_record
        self.ignore_hosts = ignore_hosts
        self.ignore_localhost = ignore_localhost

    def _get_serializer(self, serializer_name):
        try:
            serializer = self.serializers[serializer_name]
        except KeyError:
            print("Serializer {0} doesn't exist or isn't registered".format(
                serializer_name
            ))
            raise KeyError
        return serializer

    def _get_matchers(self, matcher_names):
        matchers = []
        try:
            for m in matcher_names:
                matchers.append(self.matchers[m])
        except KeyError:
            raise KeyError(
                "Matcher {0} doesn't exist or isn't registered".format(
                    m)
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
            "filter_headers": kwargs.get(
                'filter_headers', self.filter_headers
            ),
            "filter_query_parameters": kwargs.get(
                'filter_query_parameters', self.filter_query_parameters
            ),
            "before_record": kwargs.get(
                "before_record", self.before_record
            ),
            "ignore_hosts": kwargs.get(
                'ignore_hosts', self.ignore_hosts
            ),
            "ignore_localhost": kwargs.get(
                'ignore_localhost', self.ignore_localhost
            ),
        }

        return Cassette.load(path, **merged_config)

    def register_serializer(self, name, serializer):
        self.serializers[name] = serializer

    def register_matcher(self, name, matcher):
        self.matchers[name] = matcher
