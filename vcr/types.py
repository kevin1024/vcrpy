"""Types for code that configures or extends vcrpy.

Hooks, matchers, serializers and persisters can be annotated with these, e.g.::

    from vcr.types import Response

    def scrub(response: Response) -> Response:
        response["headers"].pop("Set-Cookie", None)
        return response

A hook can also leave the response type to vcrpy with a type parameter::

    def log_it[R](response: R) -> R:
        print(response)
        return response

So that these types can all be imported from here, it also has ``CassetteContextDecorator``
and ``InjectingCassetteContextDecorator`` of ``vcr.cassette``, and ``Readable`` and
``SupportsKeysAndGetItem`` of ``vcr.request``.
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from io import BytesIO
from typing import Literal, NotRequired, Protocol, TypeAlias, TypedDict

from .cassette import Cassette, CassetteContextDecorator, InjectingCassetteContextDecorator
from .record_mode import RecordMode
from .request import Readable, Request, SupportsKeysAndGetItem

if sys.version_info >= (3, 13):
    from typing import TypeVar
else:
    from typing_extensions import TypeVar

__all__ = [
    "JSON",
    "BodyChunk",
    "CassetteArgs",
    "CassetteConfig",
    "CassetteContextDecorator",
    "CassetteDict",
    "CassetteOptions",
    "CustomPatch",
    "FormFields",
    "FuncPathGenerator",
    "HeaderValue",
    "HeadersIn",
    "InjectingCassetteContextDecorator",
    "Interaction",
    "InteractionHook",
    "LoadedCassette",
    "Matcher",
    "MatcherFailure",
    "Metadata",
    "OneOrMany",
    "PatcherName",
    "PathTransformer",
    "Persister",
    "Readable",
    "RecordModeLike",
    "Replacement",
    "Replacer",
    "RequestBody",
    "RequestBodyIn",
    "RequestDict",
    "RequestFilter",
    "Response",
    "ResponseBody",
    "ResponseFilter",
    "SensitiveData",
    "SensitiveValue",
    "SerializedCassette",
    "SerializedInteraction",
    "SerializedRequest",
    "SerializedResponse",
    "SerializedResponseBody",
    "Serializer",
    "SimilarRequest",
    "Status",
    "StrPath",
    "SupportsKeysAndGetItem",
    "UseCassetteOptions",
    "VCROptions",
]

_T = TypeVar("_T")
_V_contra = TypeVar("_V_contra", contravariant=True, default=object)

JSON: TypeAlias = bool | int | float | str | list["JSON"] | dict[str, "JSON"] | None
"""A value that can be stored in a cassette, e.g. as metadata."""

StrPath: TypeAlias = str | os.PathLike[str]

OneOrMany: TypeAlias = _T | Iterable[_T]
"""Hook options take one function or several, which run in order."""

RecordModeLike: TypeAlias = RecordMode | Literal["all", "any", "new_episodes", "none", "once"]
"""A record mode, as a ``RecordMode`` (``vcr.mode``) or its value."""

PatcherName: TypeAlias = Literal[
    "httplib",
    "requests",
    "boto3",
    "urllib3",
    "httplib2",
    "tornado",
    "aiohttp",
    "httpx",
    "httpx2",
]
"""The HTTP libraries vcrpy patches, which ``skip_patchers`` can name."""

Metadata: TypeAlias = dict[str, JSON]
"""The values stored in a cassette with ``Cassette.get_metadata``, by key."""


# Requests


BodyChunk: TypeAlias = bytes | bytearray | memoryview | str | int
"""An item of an iterable body: all of them str, all bytes-like, or all byte values."""

FormFields: TypeAlias = dict[str, object] | list[tuple[str, object]]
"""Form data, as aiohttp records it."""

RequestBody: TypeAlias = bytes | bytearray | BytesIO | Iterator[BodyChunk] | FormFields | None
"""What ``Request.body`` returns: a file-like body as a fresh ``BytesIO`` each time, an
iterable body as a fresh iterator, a str as UTF-8 bytes."""

RequestBodyIn: TypeAlias = (
    RequestBody | str | Readable | Iterator[BodyChunk] | tuple[BodyChunk, ...] | memoryview
)
"""What ``Request(body=...)`` and ``request.body = ...`` take. An iterator or tuple of chunks is
kept as chunks, and a memoryview as its byte values."""

HeaderValue: TypeAlias = str | bytes | list[str] | list[bytes] | list[str | bytes] | tuple[str | bytes, ...]
"""A request header value. Of a list or tuple of values, a request keeps only the first.
Some libraries, like requests, allow bytes values."""

HeadersIn: TypeAlias = SupportsKeysAndGetItem[str, HeaderValue] | Iterable[tuple[str, HeaderValue]]
"""Request headers: a mapping, or (name, value) pairs."""


class RequestDict(TypedDict):
    """A request as ``Request._to_dict`` and ``Request._from_dict`` represent it."""

    method: str
    uri: str
    body: RequestBody
    headers: dict[str, list[str | bytes]]


# Responses


class Status(TypedDict):
    """The status of a recorded response."""

    code: int
    message: NotRequired[str]  # Cassettes recorded with httpx before vcrpy 8.2 have no message


class ResponseBody(TypedDict, total=False):
    """The body of a recorded response."""

    string: bytes | None  # aiohttp records a response without a body as {}


class Response(TypedDict):
    """A recorded response, as ``before_record_response`` and the interaction hooks get it."""

    status: Status
    headers: dict[str, list[str]]
    body: ResponseBody
    url: NotRequired[str]


Interaction: TypeAlias = tuple[Request, Response]
"""A request and the response recorded for it."""


# Hooks and matchers


Matcher: TypeAlias = Callable[[Request, Request], bool | None]
"""Compares the request being made with a recorded one. It fails by returning False or by
raising AssertionError, whose message explains the difference."""

MatcherFailure: TypeAlias = tuple[str, str | None]
"""The name of a matcher that failed, and its AssertionError message if it raised one."""

SimilarRequest: TypeAlias = tuple[Request, list[str], list[MatcherFailure]]
"""A recorded request, the names of the matchers it passed, and the matchers it failed."""

RequestFilter: TypeAlias = Callable[[Request], Request | None]
"""A ``before_record_request`` hook. Returning None leaves the request out of the cassette."""

ResponseFilter: TypeAlias = Callable[[Response], Response | None]
"""A ``before_record_response`` hook. Returning None leaves the interaction out of the cassette."""

InteractionHook: TypeAlias = (
    Callable[[Request, Response], Interaction | None]
    | Callable[[Request, Response, Cassette], Interaction | None]
)
"""A ``before_save_interaction`` or ``after_load_interaction`` hook. Returning None drops the interaction."""


class Replacer(Protocol[_V_contra]):
    """Computes the replacement for a filtered header, query parameter or body parameter.

    Returning None removes it.
    """

    def __call__(self, *, key: str, value: _V_contra, request: Request) -> str | None: ...


Replacement: TypeAlias = str | Replacer[_T] | None
"""A fixed replacement, a function that computes one, or None to remove the value."""

SensitiveValue: TypeAlias = str | int | Callable[[Request, Response], str | int | None] | None
"""A value to hide behind a placeholder, or a function of the interaction that returns it.
None, or an empty value, is skipped."""

SensitiveData: TypeAlias = (
    Mapping[str, SensitiveValue] | list[tuple[str, SensitiveValue]] | tuple[tuple[str, SensitiveValue], ...]
)
"""Placeholders and the values they stand for."""

PathTransformer: TypeAlias = Callable[[StrPath], StrPath]
"""Changes the path of a cassette before it's loaded, like ``VCR.ensure_suffix(".yaml")``."""

FuncPathGenerator: TypeAlias = Callable[[Callable[..., object]], StrPath]
"""Names the cassette of a decorated function."""

CustomPatch: TypeAlias = tuple[object, str, object]
"""An object, the name of an attribute of it, and the VCR stub to patch it with."""


# Serializers and persisters


class SerializedRequest(TypedDict):
    """A request as it's stored in a cassette. A body that's valid UTF-8 is a str."""

    method: str
    uri: str
    body: str | RequestBody
    headers: dict[str, list[str | bytes]]


class SerializedResponseBody(TypedDict, total=False):
    """The body of a response as it's stored in a cassette. A body that's valid UTF-8 is a str."""

    string: str | bytes | None


class SerializedResponse(TypedDict):
    """A response as it's stored in a cassette."""

    status: Status
    headers: dict[str, list[str]]
    body: SerializedResponseBody
    url: NotRequired[str]


class SerializedInteraction(TypedDict):
    """A request and its response as they're stored in a cassette."""

    request: SerializedRequest
    response: SerializedResponse


class SerializedCassette(TypedDict):
    """What serializers turn into text and back. Bodies that are valid UTF-8 are str."""

    version: int
    interactions: list[SerializedInteraction]
    metadata: NotRequired[Metadata]


class Serializer(Protocol):
    """Turns cassettes into text and back. The json and yaml serializer modules are Serializers."""

    def serialize(self, cassette_dict: SerializedCassette, /) -> str: ...

    def deserialize(self, cassette_string: str, /) -> SerializedCassette: ...


class CassetteDict(TypedDict):
    """What a cassette gives its persister to save."""

    requests: list[Request]
    responses: list[Response]
    metadata: NotRequired[Metadata]


LoadedCassette: TypeAlias = (
    tuple[Sequence[Request], Sequence[Response]] | tuple[Sequence[Request], Sequence[Response], Metadata]
)
"""What a persister loads: requests and responses, and the metadata if the cassette has any."""


class Persister(Protocol):
    """Loads and saves cassettes. It's registered as a class, so it implements these as
    class or static methods. ``load_cassette`` raises ``CassetteNotFoundError`` for a missing
    cassette, and ``CassetteDecodeError`` for one it can't read; both are in
    ``vcr.persisters.filesystem``."""

    def load_cassette(self, cassette_path: StrPath, serializer: Serializer) -> LoadedCassette: ...

    def save_cassette(
        self,
        cassette_path: StrPath,
        cassette_dict: CassetteDict,
        serializer: Serializer,
    ) -> None: ...


# Options


class _SharedOptions(TypedDict, total=False):
    path_transformer: PathTransformer | None
    before_record_request: OneOrMany[RequestFilter] | None
    before_record: OneOrMany[RequestFilter] | None
    custom_patches: Iterable[CustomPatch]
    filter_query_parameters: Iterable[str | tuple[str, Replacement[str]]]
    ignore_hosts: Iterable[str | re.Pattern[str]]
    record_mode: RecordModeLike
    ignore_localhost: bool
    filter_headers: Iterable[str | tuple[str, Replacement[str | bytes]]]
    before_record_response: OneOrMany[ResponseFilter] | None
    filter_post_data_parameters: Iterable[str | tuple[str, Replacement[object]]]
    filter_nested_post_data_parameters: bool
    match_on: Iterable[str]
    serializer: str
    cassette_library_dir: StrPath | None
    func_path_generator: FuncPathGenerator | None
    decode_compressed_response: bool
    record_on_exception: bool
    drop_unused_requests: bool
    filter_sensitive_data: SensitiveData
    before_save_interaction: OneOrMany[InteractionHook] | None
    after_load_interaction: OneOrMany[InteractionHook] | None
    skip_patchers: Iterable[PatcherName]


class _PerCassetteOptions(TypedDict, total=False):
    additional_matchers: Iterable[str]
    allow_playback_repeats: bool
    persister: Persister


class VCROptions(_SharedOptions, total=False):
    """The keyword arguments of ``VCR()``."""

    inject_cassette: bool


class CassetteOptions(VCROptions, _PerCassetteOptions, total=False):
    """The keyword arguments of ``use_cassette()``."""


class UseCassetteOptions(_SharedOptions, _PerCassetteOptions, total=False):
    """``CassetteOptions`` without ``inject_cassette``, which ``use_cassette`` takes separately,
    as it determines the type of what it returns."""


class CassetteArgs(TypedDict, total=False):
    """The keyword arguments of ``Cassette()`` after the path."""

    serializer: Serializer | None
    persister: Persister | None
    record_mode: RecordMode
    match_on: Sequence[Matcher]
    before_record_request: RequestFilter | None
    before_record_response: ResponseFilter | None
    custom_patches: Iterable[CustomPatch]
    inject: bool
    allow_playback_repeats: bool
    drop_unused_requests: bool
    filter_sensitive_data: SensitiveData
    before_save_interaction: OneOrMany[InteractionHook] | None
    after_load_interaction: OneOrMany[InteractionHook] | None
    skip_patchers: Iterable[PatcherName]


class CassetteConfig(CassetteArgs, total=False):
    """The configuration of a cassette, as ``VCR.get_merged_config`` returns it."""

    path: StrPath
    path_transformer: PathTransformer | None
    func_path_generator: FuncPathGenerator | None
    record_on_exception: bool
