import collections
import copy
import functools
import os

from .cassette import Cassette
from .serializers import yamlserializer, jsonserializer
from . import matchers
from . import filters


class VCR(object):

    def __init__(self, serializer='yaml', cassette_library_dir=None,
                 record_mode="once", filter_headers=(), ignore_localhost=False,
                 custom_patches=(), filter_query_parameters=(),
                 filter_post_data_parameters=(), before_record_request=None,
                 before_record_response=None, ignore_hosts=(),
                 match_on=('method', 'scheme', 'host', 'port', 'path', 'query'),
                 before_record=None, inject_cassette=False):
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
        self.filter_post_data_parameters = filter_post_data_parameters
        self.before_record_request = before_record_request or before_record
        self.before_record_response = before_record_response
        self.ignore_hosts = ignore_hosts
        self.ignore_localhost = ignore_localhost
        self.inject_cassette = inject_cassette
        self._custom_patches = tuple(custom_patches)

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
                "Matcher {0} doesn't exist or isn't registered".format(m)
            )
        return matchers

    def use_cassette(self, path, with_current_defaults=False, **kwargs):
        if with_current_defaults:
            path, config = self.get_path_and_merged_config(path, **kwargs)
            return Cassette.use(path, **config)
        # This is made a function that evaluates every time a cassette
        # is made so that changes that are made to this VCR instance
        # that occur AFTER the `use_cassette` decorator is applied
        # still affect subsequent calls to the decorated function.
        args_getter = functools.partial(self.get_path_and_merged_config,
                                        path, **kwargs)
        return Cassette.use_arg_getter(args_getter)

    def get_path_and_merged_config(self, path, **kwargs):
        serializer_name = kwargs.get('serializer', self.serializer)
        matcher_names = kwargs.get('match_on', self.match_on)
        cassette_library_dir = kwargs.get(
            'cassette_library_dir',
            self.cassette_library_dir
        )
        if cassette_library_dir:
            path = os.path.join(cassette_library_dir, path)

        merged_config = {
            'serializer': self._get_serializer(serializer_name),
            'match_on': self._get_matchers(matcher_names),
            'record_mode': kwargs.get('record_mode', self.record_mode),
            'before_record_request': self._build_before_record_request(kwargs),
            'before_record_response': self._build_before_record_response(
                kwargs
            ),
            'custom_patches': self._custom_patches + kwargs.get(
                'custom_patches', ()
            ),
            'inject': kwargs.get('inject_cassette', self.inject_cassette)
        }
        return path, merged_config

    def _build_before_record_response(self, options):
        before_record_response = options.get(
            'before_record_response', self.before_record_response
        )
        filter_functions = []
        if before_record_response and not isinstance(before_record_response,
                                                     collections.Iterable):
            before_record_response = (before_record_response,)
            for function in before_record_response:
                filter_functions.append(function)
        def before_record_response(response):
            for function in filter_functions:
                if response is None:
                    break
                response = function(response)
            return response
        return before_record_response

    def _build_before_record_request(self, options):
        filter_functions = []
        filter_headers = options.get(
            'filter_headers', self.filter_headers
        )
        filter_query_parameters = options.get(
            'filter_query_parameters', self.filter_query_parameters
        )
        filter_post_data_parameters = options.get(
            'filter_post_data_parameters', self.filter_post_data_parameters
        )
        before_record_request = options.get(
            "before_record_request", options.get("before_record", self.before_record_request)
        )
        ignore_hosts = options.get(
            'ignore_hosts', self.ignore_hosts
        )
        ignore_localhost = options.get(
            'ignore_localhost', self.ignore_localhost
        )
        if filter_headers:
            filter_functions.append(functools.partial(filters.remove_headers,
                                                      headers_to_remove=filter_headers))
        if filter_query_parameters:
            filter_functions.append(functools.partial(filters.remove_query_parameters,
                                                      query_parameters_to_remove=filter_query_parameters))
        if filter_post_data_parameters:
            filter_functions.append(functools.partial(filters.remove_post_data_parameters,
                                                      post_data_parameters_to_remove=filter_post_data_parameters))

        hosts_to_ignore = list(ignore_hosts)
        if ignore_localhost:
            hosts_to_ignore.extend(('localhost', '0.0.0.0', '127.0.0.1'))

        if hosts_to_ignore:
            hosts_to_ignore = set(hosts_to_ignore)
            filter_functions.append(self._build_ignore_hosts(hosts_to_ignore))

        if before_record_request:
            if not isinstance(before_record_request, collections.Iterable):
                before_record_request = (before_record_request,)
            for function in before_record_request:
                filter_functions.append(function)
        def before_record_request(request):
            request = copy.copy(request)
            for function in filter_functions:
                if request is None:
                    break
                request = function(request)
            return request

        return before_record_request

    @staticmethod
    def _build_ignore_hosts(hosts_to_ignore):
        def filter_ignored_hosts(request):
            if hasattr(request, 'host') and request.host in hosts_to_ignore:
                return
            return request
        return filter_ignored_hosts

    def register_serializer(self, name, serializer):
        self.serializers[name] = serializer

    def register_matcher(self, name, matcher):
        self.matchers[name] = matcher
