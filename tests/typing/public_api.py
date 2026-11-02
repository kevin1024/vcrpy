"""How code that uses vcrpy type-checks. mypy and pyright check this file; it isn't run.

Each ``# type: ignore[...]`` marks a call that must stay an error. Both checkers report
an ignore that's no longer needed; pyright treats it as ignoring any error on its line.
"""

# pyright: reportUnnecessaryTypeIgnoreComment=error

from __future__ import annotations

import re
from collections.abc import Iterator
from io import BytesIO
from typing import Literal, TypeVar, Unpack, assert_type

import vcr
from vcr import VCR, Request
from vcr.cassette import Cassette, CassetteContextDecorator
from vcr.errors import CannotOverwriteExistingCassetteException
from vcr.persisters.filesystem import FilesystemPersister
from vcr.record_mode import RecordMode
from vcr.request import HeadersDict, SupportsKeysAndGetItem
from vcr.serializers import jsonserializer, yamlserializer
from vcr.types import (
    JSON,
    InjectingCassetteContextDecorator,
    Interaction,
    Replacer,
    RequestBody,
    Response,
    SerializedCassette,
    SimilarRequest,
    VCROptions,
)
from vcr.unittest import VCRTestCase
from vcr.util import CaseInsensitiveDict

_R = TypeVar("_R")

my_vcr = VCR(
    record_mode="new_episodes",
    match_on=["method", "uri"],
    filter_headers=["authorization", ("x-api-key", "XXX")],
    filter_query_parameters=[("token", lambda key, value, request: value[:2])],
    ignore_hosts=["localhost", re.compile(r".*\.internal")],
    skip_patchers=["httpx"],
)
assert_type(my_vcr.record_mode, RecordMode)

VCR(record_mode="sometimes")  # type: ignore[arg-type]
VCR(skip_patchers=["curl"])  # type: ignore[list-item]
VCR(match_on="method")  # str is an Iterable[str]; a known gap, the names are checked at runtime


# Context manager


assert_type(vcr.use_cassette("fixtures/a.yaml"), CassetteContextDecorator[Cassette])
assert_type(vcr.mode.ONCE, Literal[RecordMode.ONCE])

with my_vcr.use_cassette("fixtures/a.yaml", record_mode=vcr.mode.ALL) as cassette:
    assert_type(cassette, Cassette)
    assert_type(cassette.requests, list[Request])
    assert_type(cassette.responses, list[Response])
    assert_type(cassette.play_count, int)
    assert_type(cassette.find_requests_with_most_matches(cassette.requests[0]), list[SimilarRequest])
    seed: JSON = cassette.get_metadata("seed", 4)

my_vcr.use_cassette("fixtures/a.yaml", record_mod="all")  # type: ignore[call-overload]


# Decorators keep the signature of what they decorate


@my_vcr.use_cassette
def fetch(url: str, retries: int = 3) -> bytes:
    return url.encode() * retries


@my_vcr.use_cassette("fixtures/b.yaml", allow_playback_repeats=True)
async def fetch_async(url: str) -> bytes:
    return url.encode()


@vcr.use_cassette("fixtures/c.yaml")
def chunks() -> Iterator[bytes]:
    yield b"chunk"


assert_type(fetch("http://example.com/"), bytes)
assert_type(chunks(), Iterator[bytes])
fetch(3)  # type: ignore[arg-type]


async def use_fetch_async() -> None:
    assert_type(await fetch_async("http://example.com/"), bytes)


# A cassette injected as the first argument


injecting = my_vcr.use_cassette("fixtures/d.yaml", inject_cassette=True)
assert_type(injecting, InjectingCassetteContextDecorator)


@injecting
def count(cassette: Cassette, extra: int) -> int:
    return len(cassette) + extra


assert_type(count(1), int)
count(cassette, 1)  # type: ignore[call-arg, arg-type]


# Hooks


def scrub(response: Response) -> Response:
    response["headers"].pop("Set-Cookie", None)
    return response


def passthrough(response: _R) -> _R:
    return response


def drop_logins(request: Request) -> Request | None:
    return None if request.path == "/login" else request


def save_hook(request: Request, response: Response, cassette: Cassette) -> Interaction | None:
    return request, response


def load_hook(request: Request, response: Response) -> Interaction:
    return request, response


VCR(
    before_record_response=[scrub, passthrough],
    before_record_request=drop_logins,
    before_save_interaction=save_hook,
    after_load_interaction=[load_hook, save_hook],
    filter_sensitive_data={"<TOKEN>": "secret", "<PORT>": lambda request, response: request.port},
)


def untyped_dict_hook(response: dict[str, str]) -> dict[str, str]:
    return response


VCR(before_record_response=untyped_dict_hook)  # type: ignore[arg-type]


# Extension points


def jurassic_matcher(r1: Request, r2: Request) -> bool:
    # Header values can be bytes, as some libraries, like requests, allow them.
    movie = r1.headers.get("X-Movie", "")
    return r1.uri == r2.uri and isinstance(movie, str) and "JURASSIC PARK" in movie


class BogoSerializer:
    def serialize(self, cassette_dict: SerializedCassette) -> str:
        return ""

    def deserialize(self, cassette_string: str) -> SerializedCassette:
        return {"version": 1, "interactions": []}


my_vcr.register_matcher("jurassic", jurassic_matcher)
my_vcr.register_serializer("json", jsonserializer)
my_vcr.register_serializer("yaml", yamlserializer)
my_vcr.register_serializer("bogo", BogoSerializer())
my_vcr.register_serializer(
    "custom",
    yamlserializer.with_custom_tags({"tag:example.com,2026:thing": lambda loader, node: None}),
)
my_vcr.register_persister(FilesystemPersister)
my_vcr.register_serializer("broken", jurassic_matcher)  # type: ignore[arg-type]


# Requests


request = Request("POST", "http://example.com/?q=1", b"body", {"Content-Type": "text/plain"})
assert_type(request.body, RequestBody)
assert_type(request.headers, HeadersDict)
assert_type(request.headers["Content-Type"], str | bytes)
assert_type(request.host, str | None)
assert_type(request.port, int | None)
assert_type(request.query, list[tuple[str, str]])
request.body = "text"
request.body = BytesIO(b"file")
request.body = iter([b"a", b"b"])
request.body = None
request.headers = {"Accept": ["text/html", "application/json"]}
request.body = 3  # type: ignore[assignment]


# Errors


def describe(error: CannotOverwriteExistingCassetteException) -> str:
    assert_type(error.similar_requests, list[SimilarRequest])
    assert_type(error.failed_request, Request | None)
    return error.reason


# unittest


class MyTest(VCRTestCase):
    def _get_vcr_kwargs(self, **kwargs: Unpack[VCROptions]) -> VCROptions:
        return {**kwargs, "record_mode": "none"}

    def test_it(self) -> None:
        assert_type(self.cassette, Cassette)


# Bare generic types mean their defaults


def bare(
    decorator: CassetteContextDecorator,
    mapping: CaseInsensitiveDict,
    source: SupportsKeysAndGetItem[str],
    replacer: Replacer,
) -> None:
    assert_type(decorator, CassetteContextDecorator[Cassette])
    assert_type(mapping, CaseInsensitiveDict[object])
    assert_type(source, SupportsKeysAndGetItem[str, object])
    assert_type(replacer, Replacer[object])


class MyCassette(Cassette):
    pass


assert_type(MyCassette.use(path="fixtures/e.yaml").__enter__(), MyCassette)
