import asyncio
import copy

import pytest

from vcr.request import HeadersDict, Request
from vcr.util import read_body


@pytest.mark.parametrize(
    "method, uri, expected_str",
    [
        ("GET", "http://www.google.com/", "<Request (GET) http://www.google.com/>"),
        ("OPTIONS", "*", "<Request (OPTIONS) *>"),
        ("CONNECT", "host.some.where:1234", "<Request (CONNECT) host.some.where:1234>"),
    ],
)
def test_str(method, uri, expected_str):
    assert str(Request(method, uri, "", {})) == expected_str


def test_headers():
    headers = {"X-Header1": ["h1"], "X-Header2": "h2"}
    req = Request("GET", "http://go.com/", "", headers)
    assert req.headers == {"X-Header1": "h1", "X-Header2": "h2"}
    req.headers["X-Header1"] = "h11"
    assert req.headers == {"X-Header1": "h11", "X-Header2": "h2"}


def test_add_header_deprecated():
    req = Request("GET", "http://go.com/", "", {})
    with pytest.deprecated_call():
        req.add_header("foo", "bar")
    assert req.headers == {"foo": "bar"}


@pytest.mark.parametrize(
    "uri, expected_port",
    [
        ("http://go.com/", 80),
        ("http://go.com:80/", 80),
        ("http://go.com:3000/", 3000),
        ("https://go.com/", 443),
        ("https://go.com:443/", 443),
        ("https://go.com:3000/", 3000),
        ("*", None),
    ],
)
def test_port(uri, expected_port):
    req = Request("GET", uri, "", {})
    assert req.port == expected_port


@pytest.mark.parametrize(
    "method, uri",
    [
        ("GET", "http://go.com/"),
        ("GET", "http://go.com:80/"),
        ("CONNECT", "localhost:1234"),
        ("OPTIONS", "*"),
    ],
)
def test_uri(method, uri):
    assert Request(method, uri, "", {}).uri == uri


def _sync_body_generator():
    yield b"hello "
    yield b"world"


def _async_body_generator():
    async def gen():
        yield b"hello "
        yield b"world"

    return gen()


def test_sync_generator_body_is_buffered_and_repeatable():
    req = Request("POST", "http://go.com/", _sync_body_generator(), {})
    assert read_body(req) == b"hello world"
    # The body was buffered on construction, so it can be read again
    # (e.g. once by a matcher and once by the serializer).
    assert read_body(req) == b"hello world"


def test_sync_generator_body_survives_deepcopy():
    req = Request("POST", "http://go.com/", _sync_body_generator(), {})
    copied = copy.deepcopy(req)
    assert read_body(copied) == b"hello world"
    assert read_body(req) == b"hello world"


def test_async_generator_body_deepcopy_does_not_raise():
    # Regression test for #974: cassette recording deepcopies the request
    # (in vcr.config's before_record_request chain), and deepcopying an
    # async generator raises "cannot pickle 'async_generator' object".
    req = Request("POST", "http://go.com/", _async_body_generator(), {})
    copied = copy.deepcopy(req)
    # The unbuffered async body is shared with the copy, not copied.
    assert copied.body is req.body


def test_async_generator_body_buffering():
    req = Request("POST", "http://go.com/", _async_body_generator(), {})

    buffered = asyncio.run(req.buffer_async_body())

    assert buffered == b"hello world"
    assert req.body == b"hello world"
    # After buffering, the body is repeatable, deepcopyable, and
    # serializable like any other bytes body.
    assert read_body(req) == b"hello world"
    assert read_body(req) == b"hello world"
    copied = copy.deepcopy(req)
    assert read_body(copied) == b"hello world"
    assert req._to_dict()["body"] == b"hello world"


def test_async_generator_body_buffering_str_chunks():
    async def gen():
        yield "hello "
        yield "world"

    req = Request("POST", "http://go.com/", gen(), {})
    assert asyncio.run(req.buffer_async_body()) == b"hello world"


def test_buffer_async_body_is_noop_for_bytes_body():
    req = Request("POST", "http://go.com/", b"hello", {})
    assert asyncio.run(req.buffer_async_body()) == b"hello"
    assert req.body == b"hello"


def test_HeadersDict():
    # Simple test of CaseInsensitiveDict
    h = HeadersDict()
    assert h == {}
    h["Content-Type"] = "application/json"
    assert h == {"Content-Type": "application/json"}
    assert h["content-type"] == "application/json"
    assert h["CONTENT-TYPE"] == "application/json"

    # Test feature of HeadersDict: devolve list to first element
    h = HeadersDict()
    assert h == {}
    h["x"] = ["foo", "bar"]
    assert h == {"x": "foo"}

    # Test feature of HeadersDict: preserve original key case
    h = HeadersDict()
    assert h == {}
    h["Content-Type"] = "application/json"
    assert h == {"Content-Type": "application/json"}
    h["content-type"] = "text/plain"
    assert h == {"Content-Type": "text/plain"}
    h["CONtent-tyPE"] = "whoa"
    assert h == {"Content-Type": "whoa"}
