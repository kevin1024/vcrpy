"""Laws of vcrpy's primitives, checked with hypothesis."""

# pyright: reportPrivateUsage=false
# Requests round-trip through Request._to_dict and Request._from_dict, as cassettes store them.

from __future__ import annotations

import json
import string
from collections.abc import Callable, Iterator
from io import BytesIO
from typing import Literal, TypeAlias, TypeVar
from urllib.parse import urlencode, urlparse

import pytest
from hypothesis import given
from hypothesis import strategies as st

from vcr import filters, serialize
from vcr.config import VCR
from vcr.request import HeadersDict, Request
from vcr.serializers import jsonserializer, yamlserializer
from vcr.types import (
    JSON,
    BodyChunk,
    CassetteDict,
    FormFields,
    HeadersIn,
    LoadedCassette,
    Matcher,
    Metadata,
    RequestBodyIn,
    Response,
    Serializer,
)
from vcr.util import read_body

# Request bodies are made fresh from a spec, as files and iterators are used up.

ChunkList: TypeAlias = list[bytes] | list[str] | list[int]
FormValue: TypeAlias = str | int
BodyKind: TypeAlias = Literal[
    "bytes",
    "bytearray",
    "file",
    "str",
    "text file",
    "none",
    "iterator",
    "tuple",
    "dict",
    "pairs",
]
BodySpec: TypeAlias = (
    tuple[Literal["bytes", "bytearray", "file"], bytes]
    | tuple[Literal["str", "text file"], str]
    | tuple[Literal["none"], None]
    | tuple[Literal["iterator", "tuple"], ChunkList]
    | tuple[Literal["dict"], dict[str, FormValue]]
    | tuple[Literal["pairs"], list[tuple[str, FormValue]]]
)

_K = TypeVar("_K", bound=BodyKind)


def kinds(*names: _K) -> st.SearchStrategy[_K]:
    """The names of kinds of bodies, typed as their literals."""
    return st.sampled_from(names)


chunk_lists: st.SearchStrategy[ChunkList] = st.one_of(
    st.lists(st.binary(max_size=8), max_size=4),
    st.lists(st.text(max_size=8), max_size=4),
    st.lists(st.integers(0, 255), max_size=8),
)
form_values: st.SearchStrategy[FormValue] = st.one_of(st.text(max_size=8), st.integers())
body_specs: st.SearchStrategy[BodySpec] = st.one_of(
    st.tuples(kinds("bytes", "bytearray", "file"), st.binary(max_size=32)),
    st.tuples(kinds("str", "text file"), st.text(max_size=32)),
    st.tuples(kinds("none"), st.none()),
    st.tuples(kinds("iterator", "tuple"), chunk_lists),
    st.tuples(kinds("dict"), st.dictionaries(st.text(max_size=4), form_values, max_size=3)),
    st.tuples(kinds("pairs"), st.lists(st.tuples(st.text(max_size=4), form_values), max_size=3)),
)


class _TextFile:
    """A file-like object without seek, which reads str."""

    def __init__(self, text: str) -> None:
        self._text = text

    def read(self) -> str:
        return self._text


def make_body(spec: BodySpec) -> RequestBodyIn:
    match spec:
        case (("bytes" | "str"), value):
            return value
        case "bytearray", value:
            return bytearray(value)
        case "file", value:
            return BytesIO(value)
        case "text file", value:
            return _TextFile(value)
        case "none", _:
            return None
        case "iterator", chunks:
            iterator: Iterator[BodyChunk] = iter(chunks)
            return iterator
        case "tuple", chunks:
            return tuple(chunks)
        case "dict", fields:
            form: dict[str, object] = dict(fields)
            return form
        case "pairs", fields:
            pairs: list[tuple[str, object]] = list(fields)
            return pairs


ViewKind: TypeAlias = Literal["bytes", "bytearray", "none", "file", "iterator", "dict", "pairs"]
View: TypeAlias = tuple[ViewKind, bytes | bytearray | FormFields | None]
"""The kind of a request's body, and its content as read_body reads it."""


def expected_view(spec: BodySpec) -> View:
    """The view of a request with a body made from spec."""
    match spec:
        case ("bytes" | "bytearray") as kind, value:
            return kind, value
        case "str", value:
            return "bytes", value.encode("utf-8")
        case "none", _:
            return "none", None
        case "file", value:
            return "file", value
        case "text file", value:
            return "file", value.encode("utf-8")
        case (("iterator" | "tuple"), chunks):
            return "iterator", _joined(chunks)
        case "dict", fields:
            form: dict[str, object] = dict(fields)
            return "dict", form
        case "pairs", fields:
            pairs: list[tuple[str, object]] = list(fields)
            return "pairs", pairs


def _joined(chunks: ChunkList) -> bytes:
    return b"".join(_chunk_bytes(chunk) for chunk in chunks)


def _chunk_bytes(chunk: bytes | str | int) -> bytes:
    match chunk:
        case str():
            return chunk.encode("utf-8")
        case int():
            return bytes([chunk])
        case _:
            return chunk


def view(request: Request) -> View:
    kind: ViewKind
    match request.body:
        case None:
            kind = "none"
        case bytes():
            kind = "bytes"
        case bytearray():
            kind = "bytearray"
        case BytesIO():
            kind = "file"
        case dict():
            kind = "dict"
        case list():
            kind = "pairs"
        case _:
            kind = "iterator"
    return kind, read_body(request)


def make_request(spec: BodySpec = ("none", None), headers: HeadersIn | None = None) -> Request:
    return Request("POST", "http://example.com/", make_body(spec), headers or {})


# Request.body is a lens onto view(request)


@given(body_specs)
def test_body_put_get(spec: BodySpec) -> None:
    request = make_request()
    request.body = make_body(spec)
    assert view(request) == expected_view(spec)


@given(body_specs)
def test_body_get_put(spec: BodySpec) -> None:
    request = make_request(spec)
    before = view(request)
    request.body = request.body
    assert view(request) == before


@given(body_specs, body_specs)
def test_body_put_put(first: BodySpec, second: BodySpec) -> None:
    request = make_request()
    request.body = make_body(first)
    request.body = make_body(second)
    assert view(request) == view(make_request(second))


@given(body_specs)
def test_body_can_be_read_again(spec: BodySpec) -> None:
    request = make_request(spec)
    assert read_body(request) == read_body(request)


@given(body_specs)
def test_body_bytes_is_the_read_body(spec: BodySpec) -> None:
    request = make_request(spec)
    assert request.body_bytes == read_body(request)


# Request.uri

hosts = st.from_regex(r"[a-z]{1,8}(\.[a-z]{2,4})?", fullmatch=True)
paths = st.lists(st.text(string.ascii_letters + string.digits + "-_", min_size=1, max_size=6), max_size=3)
queries = st.lists(st.tuples(st.text(string.ascii_lowercase, max_size=4), st.text(max_size=4)), max_size=3)


@st.composite
def uris(draw: st.DrawFn) -> str:
    scheme = draw(st.sampled_from(["http", "https"]))
    port = draw(st.none() | st.integers(1, 65535))
    netloc = draw(hosts) + ("" if port is None else f":{port}")
    path = "".join("/" + segment for segment in draw(paths))
    query = urlencode(draw(queries))
    return f"{scheme}://{netloc}{path}" + (f"?{query}" if query else "")


@given(uris(), uris())
def test_uri_put_get(first: str, uri: str) -> None:
    request = Request("GET", first, None, {})
    request.uri = uri
    parsed = urlparse(uri)
    assert request.uri == uri
    assert request.parsed_uri == parsed
    assert (request.scheme, request.host, request.path) == (parsed.scheme, parsed.hostname, parsed.path)
    assert request.port == (parsed.port or {"http": 80, "https": 443}[parsed.scheme])


# HeadersDict

header_names = st.text(string.ascii_letters + "-", min_size=1, max_size=8)
header_values = st.text(max_size=8)


@given(header_names, header_values)
def test_headers_are_case_insensitive(name: str, value: str) -> None:
    headers = HeadersDict({name: value})
    assert headers[name.swapcase()] == headers[name.upper()] == value


@given(header_names, header_values, header_values)
def test_headers_keep_the_first_of_several_values(name: str, value: str, other: str) -> None:
    assert HeadersDict({name: [value, other]}) == HeadersDict({name: value})
    assert HeadersDict({name: (value, other)}) == HeadersDict({name: value})


@given(header_names, header_values, header_values)
def test_headers_keep_the_case_they_were_first_set_with(name: str, value: str, other: str) -> None:
    headers = HeadersDict({name: value})
    headers[name.swapcase()] = other
    assert list(headers) == [name]
    assert headers[name] == other


# Request dicts round-trip


@given(
    st.sampled_from(["GET", "POST", "PUT"]),
    uris(),
    body_specs,
    st.dictionaries(header_names, header_values),
)
def test_request_dict_round_trip(method: str, uri: str, spec: BodySpec, headers: dict[str, str]) -> None:
    request = Request(method, uri, make_body(spec), headers)
    again = Request._from_dict(request._to_dict())
    assert (again.method, again.uri, again.headers, view(again)) == (
        request.method,
        request.uri,
        request.headers,
        view(request),
    )


# Serializers round-trip


def _json_containers(children: st.SearchStrategy[JSON]) -> st.SearchStrategy[JSON]:
    return st.lists(children, max_size=3) | st.dictionaries(st.text(max_size=4), children, max_size=3)


json_values: st.SearchStrategy[JSON] = st.recursive(
    st.none() | st.booleans() | st.integers() | st.floats(allow_nan=False) | st.text(max_size=8),
    _json_containers,
    max_leaves=8,
)


BINARY = st.binary(max_size=32)
TEXT = st.text(max_size=8)


@st.composite
def responses(
    draw: st.DrawFn,
    body: st.SearchStrategy[bytes] = BINARY,
    text: st.SearchStrategy[str] = TEXT,
) -> Response:
    return {
        "status": {"code": draw(st.integers(100, 599)), "message": draw(text)},
        "headers": draw(st.dictionaries(header_names, st.lists(text, min_size=1, max_size=2), max_size=3)),
        "body": {"string": draw(body)},
    }


@st.composite
def cassette_dicts(
    draw: st.DrawFn,
    request_body_specs: st.SearchStrategy[BodySpec],
    response_bodies: st.SearchStrategy[bytes],
) -> CassetteDict:
    pairs = draw(
        st.lists(
            st.tuples(
                st.builds(
                    Request,
                    st.sampled_from(["GET", "POST"]),
                    uris(),
                    request_body_specs.map(make_body),
                    st.dictionaries(header_names, header_values, max_size=2),
                ),
                responses(response_bodies),
            ),
            max_size=3,
        ),
    )
    cassette_dict: CassetteDict = {"requests": [r for r, _ in pairs], "responses": [r for _, r in pairs]}
    if metadata := draw(st.dictionaries(st.text(max_size=4), json_values, max_size=2)):
        cassette_dict["metadata"] = metadata
    return cassette_dict


Comparable: TypeAlias = tuple[list[tuple[str, str, dict[str, str | bytes], View]], list[Response], Metadata]


def _comparable(loaded: LoadedCassette) -> Comparable:
    metadata: Metadata
    match loaded:
        case requests, responses:
            metadata = {}
        case requests, responses, metadata:
            pass
    return (
        [(r.method, r.uri, dict(r.headers), view(r)) for r in requests],
        list(responses),
        metadata,
    )


yaml_request_bodies = body_specs.filter(lambda spec: spec[0] not in ("dict", "pairs", "bytearray"))


@pytest.mark.parametrize(
    ("serializer", "request_bodies", "response_bodies"),
    [
        (yamlserializer, yaml_request_bodies, st.binary(max_size=32)),
        (yamlserializer.with_custom_tags({}), yaml_request_bodies, st.binary(max_size=32)),
        (
            jsonserializer,
            st.tuples(kinds("str"), st.text(max_size=32)),
            st.text(max_size=32).map(lambda text: text.encode("utf-8")),
        ),
    ],
)
def test_serialize_round_trip(
    serializer: Serializer,
    request_bodies: st.SearchStrategy[BodySpec],
    response_bodies: st.SearchStrategy[bytes],
) -> None:
    @given(cassette_dicts(request_bodies, response_bodies))
    def round_trip(cassette_dict: CassetteDict) -> None:
        expected = _comparable(
            (cassette_dict["requests"], cassette_dict["responses"], cassette_dict.get("metadata", {})),
        )
        text = serialize.serialize(cassette_dict, serializer)
        assert _comparable(serialize.deserialize(text, serializer)) == expected

    round_trip()


# Matchers

matcher_requests = st.builds(
    Request,
    st.sampled_from(["GET", "POST"]),
    uris(),
    st.one_of(
        st.none(),
        st.binary(max_size=16),
        st.dictionaries(st.text(max_size=4), st.integers(), max_size=2).map(lambda d: json.dumps(d).encode()),
    ),
    st.fixed_dictionaries(
        {},
        optional={"Content-Type": st.sampled_from(["application/json", "application/x-www-form-urlencoded"])},
    ),
)


def _passes(matcher: Matcher, r1: Request, r2: Request) -> bool:
    try:
        return matcher(r1, r2) in (None, True)
    except AssertionError:
        return False


@pytest.mark.parametrize("name", sorted(VCR().matchers))
@given(request=matcher_requests)
def test_matchers_are_reflexive(name: str, request: Request) -> None:
    assert _passes(VCR().matchers[name], request, request)


@pytest.mark.parametrize("name", sorted(VCR().matchers))
@given(first=matcher_requests, second=matcher_requests)
def test_matchers_are_symmetric(name: str, first: Request, second: Request) -> None:
    matcher = VCR().matchers[name]
    assert _passes(matcher, first, second) == _passes(matcher, second, first)


# Filters

form_keys = st.text(string.ascii_lowercase, min_size=1, max_size=4)
form_bodies = st.lists(st.tuples(form_keys, st.text(string.ascii_letters, max_size=4)), max_size=4).map(
    urlencode,
)


@st.composite
def filtered_requests(draw: st.DrawFn) -> Request:
    query = urlencode(draw(st.lists(st.tuples(form_keys, st.text(max_size=4)), max_size=3)))
    headers = draw(st.dictionaries(header_names, header_values, max_size=3))
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    return Request("POST", f"http://example.com/?{query}", draw(form_bodies), headers)


State: TypeAlias = tuple[
    str | None,
    str,
    list[tuple[str, str]],
    dict[str, str | bytes],
    bytes | bytearray | FormFields | None,
]


def _state(request: Request) -> State:
    # The parsed query: replace_query_parameters encodes the query again, and leaves out
    # an empty one and parameters without a value.
    return request.host, request.path, request.query, dict(request.headers), read_body(request)


Replacements: TypeAlias = list[tuple[str, str | None]]
Filter: TypeAlias = Callable[[Request, Replacements], Request]
Remover: TypeAlias = Callable[[Request, list[str]], Request]

replacements: st.SearchStrategy[Replacements] = st.lists(
    st.tuples(form_keys, st.none() | st.text(string.ascii_letters, max_size=4)),
    max_size=3,
)
FILTERS: list[Filter] = [
    filters.replace_headers,
    filters.replace_query_parameters,
    filters.replace_body_parameters,
]


@pytest.mark.parametrize("replace", FILTERS)
@given(request=filtered_requests())
def test_filters_without_replacements_change_nothing(replace: Filter, request: Request) -> None:
    before = _state(request)
    assert _state(replace(request, [])) == before


@pytest.mark.parametrize("replace", FILTERS)
@given(request=filtered_requests(), replacements=replacements)
def test_filters_are_idempotent(replace: Filter, request: Request, replacements: Replacements) -> None:
    once = _state(replace(request, replacements))
    assert _state(replace(request, replacements)) == once


REMOVERS: list[tuple[Remover, Filter]] = [
    (filters.remove_headers, filters.replace_headers),
    (filters.remove_query_parameters, filters.replace_query_parameters),
    (filters.remove_post_data_parameters, filters.replace_post_data_parameters),
]


@pytest.mark.parametrize(("remove", "replace"), REMOVERS)
@given(first=filtered_requests(), keys=st.lists(form_keys, max_size=3))
def test_removing_is_replacing_with_none(
    remove: Remover,
    replace: Filter,
    first: Request,
    keys: list[str],
) -> None:
    second = Request._from_dict(first._to_dict())
    assert _state(remove(first, keys)) == _state(replace(second, [(k, None) for k in keys]))


# replace_text and filter_sensitive_data

Nested: TypeAlias = (
    str | bytes | bytearray | int | list["Nested"] | tuple["Nested", ...] | dict[str, "Nested"]
)


def _nested_containers(children: st.SearchStrategy[Nested]) -> st.SearchStrategy[Nested]:
    return (
        st.lists(children, max_size=3)
        | st.lists(children, max_size=3).map(tuple)
        | st.dictionaries(st.text(max_size=4), children, max_size=3)
    )


nested: st.SearchStrategy[Nested] = st.recursive(
    st.text(max_size=6) | st.binary(max_size=6) | st.binary(max_size=6).map(bytearray) | st.integers(),
    _nested_containers,
    max_leaves=8,
)

Shape: TypeAlias = type[object] | tuple[type[object], list["Shape"]] | tuple[type[object], list[str]]


def _types(obj: Nested) -> Shape:
    """The types in obj, at any depth. Dict keys are left out, as replacing can merge them."""
    match obj:
        case list() | tuple():
            return type(obj), [_types(element) for element in obj]
        case dict():
            return type(obj), sorted(repr(_types(value)) for value in obj.values())
        case _:
            return type(obj)


def _has_dict(obj: Nested) -> bool:
    match obj:
        case dict():
            return True
        case list() | tuple():
            return any(map(_has_dict, obj))
        case _:
            return False


@given(nested, st.text(min_size=1, max_size=3), st.text(max_size=3))
def test_replace_text_keeps_types(obj: Nested, text: str, replacement: str) -> None:
    replaced = filters.replace_text(obj, text, replacement)
    assert type(replaced) is type(obj)
    if not _has_dict(obj):
        assert _types(replaced) == _types(obj)


@given(nested, st.text(min_size=1, max_size=3))
def test_replace_text_with_itself_changes_nothing(obj: Nested, text: str) -> None:
    assert filters.replace_text(obj, text, text) == obj


data_text = st.text("abcdefghijklm", max_size=12)


@given(
    st.tuples(uris(), data_text.map(str.encode), st.dictionaries(header_names, data_text, max_size=2)),
    responses(body=data_text.map(str.encode), text=data_text),
    st.dictionaries(
        st.text("xyz", min_size=1, max_size=3).map(lambda p: f"<{p}>"),
        st.text("nopq", min_size=2, max_size=4),
    ),
)
def test_sensitive_data_round_trip(
    request_parts: tuple[str, bytes, dict[str, str]],
    response: Response,
    sensitive_data: dict[str, str],
) -> None:
    uri, body, headers = request_parts
    request = Request("POST", uri, body, headers)
    hide, restore = filters.sensitive_data_hooks(sensitive_data)
    restored_request, restored_response = restore(*hide(request, response))
    assert restored_request._to_dict() == request._to_dict()
    assert restored_response == response
