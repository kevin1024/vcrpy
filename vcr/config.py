from __future__ import annotations

import copy
import functools
import inspect
import os
import re
import types
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Literal, ParamSpec, TypeVar, Unpack, overload

from . import filters, matchers
from .cassette import Cassette
from .patch import validate_skip_patchers
from .persisters.filesystem import FilesystemPersister
from .record_mode import RecordMode, validate_record_mode
from .serializers import jsonserializer, yamlserializer
from .util import as_list, auto_decorate, compose

if TYPE_CHECKING:
    from .cassette import CassetteContextDecorator, InjectingCassetteContextDecorator
    from .request import Request
    from .types import (
        CassetteConfig,
        CustomPatch,
        FuncPathGenerator,
        InteractionHook,
        Matcher,
        OneOrMany,
        PatcherName,
        PathTransformer,
        Persister,
        RecordModeLike,
        Replacement,
        RequestFilter,
        Response,
        ResponseFilter,
        SensitiveData,
        Serializer,
        StrPath,
        UseCassetteOptions,
    )

_P = ParamSpec("_P")
_R = TypeVar("_R")


class VCR:
    @staticmethod
    def is_test_method(method_name: str, function: object) -> bool:
        return method_name.startswith("test") and isinstance(function, types.FunctionType)

    @staticmethod
    def ensure_suffix(suffix: str) -> Callable[[StrPath], str]:
        def ensure(path: StrPath) -> str:
            path = os.fspath(path)
            if not path.endswith(suffix):
                return path + suffix
            return path

        return ensure

    def __init__(
        self,
        path_transformer: PathTransformer | None = None,
        before_record_request: OneOrMany[RequestFilter] | None = None,
        custom_patches: Iterable[CustomPatch] = (),
        filter_query_parameters: Iterable[str | tuple[str, Replacement[str]]] = (),
        ignore_hosts: Iterable[str | re.Pattern[str]] = (),
        record_mode: RecordModeLike = RecordMode.ONCE,
        ignore_localhost: bool = False,
        filter_headers: Iterable[str | tuple[str, Replacement[str | bytes]]] = (),
        before_record_response: OneOrMany[ResponseFilter] | None = None,
        filter_post_data_parameters: Iterable[str | tuple[str, Replacement[object]]] = (),
        filter_nested_post_data_parameters: bool = False,
        match_on: Iterable[str] = ("method", "scheme", "host", "port", "path", "query"),
        before_record: OneOrMany[RequestFilter] | None = None,
        inject_cassette: bool = False,
        serializer: str = "yaml",
        cassette_library_dir: StrPath | None = None,
        func_path_generator: FuncPathGenerator | None = None,
        decode_compressed_response: bool = False,
        record_on_exception: bool = True,
        drop_unused_requests: bool = False,
        filter_sensitive_data: SensitiveData = (),
        before_save_interaction: OneOrMany[InteractionHook] | None = None,
        after_load_interaction: OneOrMany[InteractionHook] | None = None,
        skip_patchers: Iterable[PatcherName] = (),
    ) -> None:
        self.serializer: str = serializer
        self.match_on: Iterable[str] = match_on
        self.cassette_library_dir: StrPath | None = cassette_library_dir
        self.serializers: dict[str, Serializer] = {"yaml": yamlserializer, "json": jsonserializer}
        self.matchers: dict[str, Matcher] = {
            "method": matchers.method,
            "uri": matchers.uri,
            "url": matchers.uri,  # matcher for backwards compatibility
            "scheme": matchers.scheme,
            "host": matchers.host,
            "port": matchers.port,
            "path": matchers.path,
            "query": matchers.query,
            "headers": matchers.headers,
            "raw_body": matchers.raw_body,
            "body": matchers.body,
        }
        self.persister: Persister = FilesystemPersister
        self.record_mode: RecordMode = validate_record_mode(record_mode)
        self.filter_headers: Iterable[str | tuple[str, Replacement[str | bytes]]] = filter_headers
        self.filter_query_parameters: Iterable[str | tuple[str, Replacement[str]]] = filter_query_parameters
        self.filter_post_data_parameters: Iterable[str | tuple[str, Replacement[object]]] = (
            filter_post_data_parameters
        )
        self.filter_nested_post_data_parameters: bool = filter_nested_post_data_parameters
        self.before_record_request: OneOrMany[RequestFilter] | None = before_record_request or before_record
        self.before_record_response: OneOrMany[ResponseFilter] | None = before_record_response
        self.ignore_hosts: Iterable[str | re.Pattern[str]] = ignore_hosts
        self.ignore_localhost: bool = ignore_localhost
        self.inject_cassette: bool = inject_cassette
        self.path_transformer: PathTransformer | None = path_transformer
        self.func_path_generator: FuncPathGenerator | None = func_path_generator
        self.decode_compressed_response: bool = decode_compressed_response
        self.record_on_exception: bool = record_on_exception
        self._custom_patches: tuple[CustomPatch, ...] = tuple(custom_patches)
        self.drop_unused_requests: bool = drop_unused_requests
        self.filter_sensitive_data: SensitiveData = filter_sensitive_data
        self.before_save_interaction: OneOrMany[InteractionHook] | None = before_save_interaction
        self.after_load_interaction: OneOrMany[InteractionHook] | None = after_load_interaction
        self.skip_patchers: tuple[PatcherName, ...] = validate_skip_patchers(skip_patchers)

    def _get_serializer(self, serializer_name: str) -> Serializer:
        try:
            serializer = self.serializers[serializer_name]
        except KeyError:
            raise KeyError(f"Serializer {serializer_name} doesn't exist or isn't registered") from None
        return serializer

    def _get_matchers(self, matcher_names: Iterable[str]) -> list[Matcher]:
        matchers = []
        for m in matcher_names:
            try:
                matchers.append(self.matchers[m])
            except KeyError:
                raise KeyError(f"Matcher {m} doesn't exist or isn't registered") from None
        return matchers

    @overload
    def use_cassette(self, path: Callable[_P, _R], /) -> Callable[_P, _R]: ...

    @overload
    def use_cassette(
        self,
        path: StrPath | None = None,
        *,
        inject_cassette: Literal[True],
        with_current_defaults: bool = False,
        **kwargs: Unpack[UseCassetteOptions],
    ) -> InjectingCassetteContextDecorator: ...

    @overload
    def use_cassette(
        self,
        path: StrPath | None = None,
        *,
        inject_cassette: Literal[False] = ...,
        with_current_defaults: bool = False,
        **kwargs: Unpack[UseCassetteOptions],
    ) -> CassetteContextDecorator[Cassette]: ...

    @overload
    def use_cassette(
        self,
        path: StrPath | None = None,
        *,
        inject_cassette: bool,
        with_current_defaults: bool = False,
        **kwargs: Unpack[UseCassetteOptions],
    ) -> CassetteContextDecorator[Cassette] | InjectingCassetteContextDecorator: ...

    def use_cassette(
        self,
        path: Callable[..., object] | StrPath | None = None,
        *,
        inject_cassette: bool | None = None,
        with_current_defaults: bool = False,
        **kwargs: Unpack[UseCassetteOptions],
    ) -> CassetteContextDecorator[Cassette] | Callable[..., object]:
        """Use a cassette, as a context manager or as a decorator.

        As a decorator without a path, it names the cassette after the decorated
        function. If the VCR (rather than this call) sets ``inject_cassette=True``,
        the decorated function's type doesn't show that it gets the cassette.
        """
        if path is not None and not isinstance(path, (str, os.PathLike)):
            function = path
            # Assume this is an attempt to decorate a function
            return self._use_cassette(None, inject_cassette, with_current_defaults, kwargs)(function)
        return self._use_cassette(path, inject_cassette, with_current_defaults, kwargs)

    def _use_cassette(
        self,
        path: StrPath | None,
        inject_cassette: bool | None,
        with_current_defaults: bool,
        options: UseCassetteOptions,
    ) -> CassetteContextDecorator[Cassette]:
        if with_current_defaults:
            config = self.get_merged_config(path=path, inject_cassette=inject_cassette, **options)
            return Cassette.use(**config)
        # This is made a function that evaluates every time a cassette
        # is made so that changes that are made to this VCR instance
        # that occur AFTER the `use_cassette` decorator is applied
        # still affect subsequent calls to the decorated function.
        args_getter = functools.partial(
            self.get_merged_config,
            path=path,
            inject_cassette=inject_cassette,
            **options,
        )
        return Cassette.use_arg_getter(args_getter)

    def get_merged_config(
        self,
        *,
        path: StrPath | None = None,
        inject_cassette: bool | None = None,
        **kwargs: Unpack[UseCassetteOptions],
    ) -> CassetteConfig:
        serializer_name = kwargs.get("serializer", self.serializer)
        matcher_names = kwargs.get("match_on", self.match_on)
        path_transformer = kwargs.get("path_transformer", self.path_transformer)
        func_path_generator = kwargs.get("func_path_generator", self.func_path_generator)
        cassette_library_dir = kwargs.get("cassette_library_dir", self.cassette_library_dir)
        additional_matchers = kwargs.get("additional_matchers", ())
        record_on_exception = kwargs.get("record_on_exception", self.record_on_exception)

        if cassette_library_dir:
            library_dir = os.fspath(cassette_library_dir)

            def add_cassette_library_dir(path: StrPath) -> StrPath:
                path = os.fspath(path)
                if not path.startswith(library_dir):
                    return os.path.join(library_dir, path)
                return path

            path_transformer = compose(add_cassette_library_dir, path_transformer)
        elif not func_path_generator:
            # If we don't have a library dir, use the functions
            # location to build a full path for cassettes.
            func_path_generator = self._build_path_from_func_using_module

        merged_config: CassetteConfig = {
            "serializer": self._get_serializer(serializer_name),
            "persister": kwargs.get("persister", self.persister),
            "match_on": self._get_matchers(tuple(matcher_names) + tuple(additional_matchers)),
            "record_mode": validate_record_mode(kwargs.get("record_mode", self.record_mode)),
            "before_record_request": self._build_before_record_request(kwargs),
            "before_record_response": self._build_before_record_response(kwargs),
            "custom_patches": self._custom_patches + tuple(kwargs.get("custom_patches", ())),
            "inject": self.inject_cassette if inject_cassette is None else inject_cassette,
            "path_transformer": path_transformer,
            "func_path_generator": func_path_generator,
            "allow_playback_repeats": kwargs.get("allow_playback_repeats", False),
            "record_on_exception": record_on_exception,
            "drop_unused_requests": kwargs.get("drop_unused_requests", self.drop_unused_requests),
            "filter_sensitive_data": kwargs.get("filter_sensitive_data", self.filter_sensitive_data),
            "before_save_interaction": kwargs.get("before_save_interaction", self.before_save_interaction),
            "after_load_interaction": kwargs.get("after_load_interaction", self.after_load_interaction),
            "skip_patchers": kwargs.get("skip_patchers", self.skip_patchers),
        }
        if path:
            merged_config["path"] = path
        return merged_config

    def _build_before_record_response(self, options: UseCassetteOptions) -> ResponseFilter:
        decode_compressed_response = options.get(
            "decode_compressed_response",
            self.decode_compressed_response,
        )
        filter_functions: list[ResponseFilter] = []
        if decode_compressed_response:
            filter_functions.append(filters.decode_response)
        filter_functions.extend(as_list(options.get("before_record_response", self.before_record_response)))

        def apply_response_filters(response: Response) -> Response | None:
            filtered: Response | None = response
            for function in filter_functions:
                if filtered is None:
                    break
                filtered = function(filtered)
            return filtered

        return apply_response_filters

    def _build_before_record_request(self, options: UseCassetteOptions) -> RequestFilter:
        filter_functions: list[RequestFilter] = []
        filter_headers = options.get("filter_headers", self.filter_headers)
        filter_query_parameters = options.get("filter_query_parameters", self.filter_query_parameters)
        filter_post_data_parameters = options.get(
            "filter_post_data_parameters",
            self.filter_post_data_parameters,
        )
        filter_nested_post_data_parameters = options.get(
            "filter_nested_post_data_parameters",
            self.filter_nested_post_data_parameters,
        )
        before_record_request = options.get(
            "before_record_request",
            options.get("before_record", self.before_record_request),
        )
        ignore_hosts = options.get("ignore_hosts", self.ignore_hosts)
        ignore_localhost = options.get("ignore_localhost", self.ignore_localhost)
        if filter_headers:
            header_replacements: list[tuple[str, Replacement[str | bytes]]] = [
                h if isinstance(h, tuple) else (h, None) for h in filter_headers
            ]
            filter_functions.append(
                functools.partial(filters.replace_headers, replacements=header_replacements),
            )
        if filter_query_parameters:
            query_replacements: list[tuple[str, Replacement[str]]] = [
                p if isinstance(p, tuple) else (p, None) for p in filter_query_parameters
            ]
            filter_functions.append(
                functools.partial(filters.replace_query_parameters, replacements=query_replacements),
            )
        if filter_post_data_parameters:
            body_replacements: list[tuple[str, Replacement[object]]] = [
                p if isinstance(p, tuple) else (p, None) for p in filter_post_data_parameters
            ]
            filter_functions.append(
                functools.partial(
                    filters.replace_body_parameters,
                    replacements=body_replacements,
                    recursive=filter_nested_post_data_parameters,
                ),
            )

        hosts_to_ignore: set[str | re.Pattern[str]] = set(ignore_hosts)
        if ignore_localhost:
            hosts_to_ignore.update(("localhost", "0.0.0.0", "127.0.0.1", "::1"))
        if hosts_to_ignore:
            filter_functions.append(self._build_ignore_hosts(hosts_to_ignore))

        filter_functions.extend(as_list(before_record_request))

        def apply_request_filters(request: Request) -> Request | None:
            filtered: Request | None = copy.deepcopy(request)
            for function in filter_functions:
                if filtered is None:
                    break
                filtered = function(filtered)
            return filtered

        return apply_request_filters

    @staticmethod
    def _build_ignore_hosts(hosts_to_ignore: Iterable[str | re.Pattern[str]]) -> RequestFilter:
        # Strings are host names; compiled patterns match whole host names.
        patterns = [host for host in hosts_to_ignore if isinstance(host, re.Pattern)]
        names = {host for host in hosts_to_ignore if not isinstance(host, re.Pattern)}

        def filter_ignored_hosts(request: Request) -> Request | None:
            host = request.host
            if host is not None and (host in names or any(pattern.fullmatch(host) for pattern in patterns)):
                return None
            return request

        return filter_ignored_hosts

    @staticmethod
    def _build_path_from_func_using_module(function: Callable[..., object]) -> str:
        name: str = getattr(function, "__name__", repr(function))
        return os.path.join(os.path.dirname(inspect.getfile(function)), name)

    def register_serializer(self, name: str, serializer: Serializer) -> None:
        self.serializers[name] = serializer

    def register_matcher(self, name: str, matcher: Matcher) -> None:
        self.matchers[name] = matcher

    def register_persister(self, persister: Persister) -> None:
        # Singleton, no name required
        self.persister = persister

    def test_case(self, predicate: Callable[[str, object], bool] | None = None) -> type:
        predicate = predicate or self.is_test_method
        metaclass = auto_decorate(self.use_cassette, predicate)
        return metaclass("temporary_class", (), {})
