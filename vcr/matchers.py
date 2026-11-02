from __future__ import annotations

import difflib
import json
import logging
import urllib.parse
import xmlrpc.client
from collections.abc import Callable, Iterable, Iterator, Sized
from string import hexdigits
from typing import TYPE_CHECKING
from xml.parsers.expat import ExpatError

from .util import _join_body_chunks, read_body

if TYPE_CHECKING:
    from .request import HeadersDict, Request
    from .types import JSON, Matcher, MatcherFailure

_HEXDIG_CODE_POINTS: set[int] = {ord(s.encode("ascii")) for s in hexdigits}

log: logging.Logger = logging.getLogger(__name__)


def method(r1: Request, r2: Request) -> None:
    if r1.method != r2.method:
        raise AssertionError(f"{r1.method} != {r2.method}")


def _normalized_path(path: str) -> str:
    """RFC 3986 section 6.2.3: an empty path is equivalent to "/"."""
    return path if path else "/"


def _normalized_uri(r: Request) -> str:
    # httpx records bare-host URLs as https://example.com; cassettes often
    # store the RFC-canonical https://example.com/. Insert the "/" so those
    # compare equal, and compare everything else exactly.
    if r.parsed_uri.path:
        return r.uri
    authority = f"{r.parsed_uri.scheme}://{r.parsed_uri.netloc}"
    if not r.uri.startswith(authority):
        return r.uri
    return authority + "/" + r.uri[len(authority) :]


def uri(r1: Request, r2: Request) -> None:
    if _normalized_uri(r1) != _normalized_uri(r2):
        raise AssertionError(f"{r1.uri} != {r2.uri}")


def host(r1: Request, r2: Request) -> None:
    if r1.host != r2.host:
        raise AssertionError(f"{r1.host} != {r2.host}")


def scheme(r1: Request, r2: Request) -> None:
    if r1.scheme != r2.scheme:
        raise AssertionError(f"{r1.scheme} != {r2.scheme}")


def port(r1: Request, r2: Request) -> None:
    if r1.port != r2.port:
        raise AssertionError(f"{r1.port} != {r2.port}")


def path(r1: Request, r2: Request) -> None:
    if _normalized_path(r1.path) != _normalized_path(r2.path):
        raise AssertionError(f"{r1.path} != {r2.path}")


def query(r1: Request, r2: Request) -> None:
    if r1.query != r2.query:
        raise AssertionError(f"{r1.query} != {r2.query}")


MAX_DIFF_LINES = 20
MAX_DIFF_LINE_LENGTH = 200


def _body_text(body: object) -> str | None:
    """Text to diff for a body, or None for a body that isn't text."""
    match body:
        case None:
            return ""
        case bytes() | bytearray():
            try:
                return body.decode("utf-8")
            except UnicodeDecodeError:
                return None
        case str():
            return body
        case _:
            # A parsed body (JSON, form data, XML-RPC): sorted keys show only real differences.
            return json.dumps(body, indent=2, sort_keys=True, default=str)


def _body_diff(new: object, recorded: object) -> str:
    """A short diff explaining how two bodies differ, for matcher failure messages.

    vcrpy calls matchers with the request being made first and the recorded one second.
    """
    new_text, recorded_text = _body_text(new), _body_text(recorded)
    if new_text is None or recorded_text is None or new_text == recorded_text:
        return f"the bodies differ ({_size(new)} in this request, {_size(recorded)} recorded)"
    diff = list(
        difflib.unified_diff(
            recorded_text.splitlines(),
            new_text.splitlines(),
            "recorded",
            "this request",
            n=1,
            lineterm="",
        ),
    )
    lines = [
        line if len(line) <= MAX_DIFF_LINE_LENGTH else line[:MAX_DIFF_LINE_LENGTH] + "…"
        for line in diff[:MAX_DIFF_LINES]
    ]
    if len(diff) > MAX_DIFF_LINES:
        lines.append(f"… ({len(diff) - MAX_DIFF_LINES} more lines)")
    return "\n".join(lines)


def _size(body: object) -> str:
    if isinstance(body, Sized):
        return f"{len(body)} bytes"
    return "no body" if body is None else type(body).__name__


def raw_body(r1: Request, r2: Request) -> None:
    b1, b2 = read_body(r1), read_body(r2)
    if b1 != b2:
        raise AssertionError(_body_diff(b1, b2))


def body(r1: Request, r2: Request) -> None:
    transformers = list(_get_transformers(r1))
    if transformers != list(_get_transformers(r2)):
        transformers = []

    b1 = read_body(r1)
    b2 = read_body(r2)
    try:
        t1: object = b1
        t2: object = b2
        for transform in transformers:
            t1 = transform(t1)
            t2 = transform(t2)
    except (ValueError, ExpatError):
        # A body that doesn't parse as its headers say (e.g. invalid JSON sent
        # as application/json) is compared as raw bytes instead.
        t1, t2 = b1, b2

    if t1 != t2:
        raise AssertionError(_body_diff(t1, t2))


def headers(r1: Request, r2: Request) -> None:
    if r1.headers != r2.headers:
        raise AssertionError(f"{r1.headers} != {r2.headers}")


def _header_checker(value: str, header: str = "Content-Type") -> Callable[[HeadersDict], bool]:
    def checker(headers: HeadersDict) -> bool:
        _header = headers.get(header, "")
        if isinstance(_header, bytes):
            _header = _header.decode("utf-8")
        return value in _header.lower()

    return checker


def _dechunk(body: object) -> object:
    match body:
        case str():
            body = body.encode("utf-8")
        case bytearray():
            body = bytes(body)
        case Iterable():
            parts = list(body)
            body = _join_body_chunks(parts) if parts else None

    if not isinstance(body, bytes):
        return body

    # Now decode chunked data format (https://en.wikipedia.org/wiki/Chunked_transfer_encoding)
    # Example input: b"45\r\n<69 bytes>\r\n0\r\n\r\n" where int(b"45", 16) == 69.
    CHUNK_GAP = b"\r\n"
    BODY_LEN: int = len(body)

    chunks: list[bytes] = []
    pos: int = 0

    while True:
        i = pos
        for i in range(pos, BODY_LEN):
            if body[i] not in _HEXDIG_CODE_POINTS:
                break

        if i == 0 or body[i : i + len(CHUNK_GAP)] != CHUNK_GAP:
            if pos == 0:
                return body  # i.e. assume non-chunk data
            raise ValueError("Malformed chunked data")

        size_bytes = int(body[pos:i], 16)
        if size_bytes == 0:  # i.e. well-formed ending
            return b"".join(chunks)

        chunk_data_first = i + len(CHUNK_GAP)
        chunk_data_after_last = chunk_data_first + size_bytes

        if body[chunk_data_after_last : chunk_data_after_last + len(CHUNK_GAP)] != CHUNK_GAP:
            raise ValueError("Malformed chunked data")

        chunk_data = body[chunk_data_first:chunk_data_after_last]
        chunks.append(chunk_data)

        pos = chunk_data_after_last + len(CHUNK_GAP)


def _transform_form(body: object) -> object:
    if isinstance(body, (bytes, bytearray)):
        return urllib.parse.parse_qs(body.decode("ascii"))
    return body


def _transform_json(body: object) -> object:
    if not body:
        return None
    if isinstance(body, (bytes, bytearray, str)):
        parsed: JSON = json.loads(body)
        return parsed
    return body


def _transform_xmlrpc(body: object) -> object:
    if isinstance(body, (bytes, bytearray, str)):
        return xmlrpc.client.loads(body)
    return body


def _is_xmlrpc(headers: HeadersDict) -> bool:
    return _xml_header_checker(headers) and _xmlrpc_header_checker(headers)


_xml_header_checker = _header_checker("text/xml")
_xmlrpc_header_checker = _header_checker("xmlrpc", header="User-Agent")
_checker_transformer_pairs: tuple[tuple[Callable[[HeadersDict], bool], Callable[[object], object]], ...] = (
    (_header_checker("chunked", header="Transfer-Encoding"), _dechunk),
    (_header_checker("application/x-www-form-urlencoded"), _transform_form),
    (_header_checker("application/json"), _transform_json),
    (_is_xmlrpc, _transform_xmlrpc),
)


def _get_transformers(request: Request) -> Iterator[Callable[[object], object]]:
    for checker, transformer in _checker_transformer_pairs:
        if checker(request.headers):
            yield transformer


def requests_match(r1: Request, r2: Request, matchers: Iterable[Matcher]) -> bool:
    _, failures = get_matchers_results(r1, r2, matchers)
    if failures:
        log.debug(f"Requests {r1} and {r2} differ.\nFailure details:\n{failures}")
    return len(failures) == 0


def _evaluate_matcher(matcher_function: Matcher, r1: Request, r2: Request) -> tuple[bool, str | None]:
    """
    Evaluate the result of a given matcher as a boolean with an assertion error message if any.
    It handles two types of matcher :
    - a matcher returning a boolean value.
    - a matcher that only makes an assert, returning None or raises an assertion error.
    """
    assertion_message = None
    try:
        match = matcher_function(r1, r2)
        match = True if match is None else match
    except AssertionError as e:
        match = False
        assertion_message = str(e)
    return match, assertion_message


def get_matchers_results(
    r1: Request,
    r2: Request,
    matchers: Iterable[Matcher],
) -> tuple[list[str], list[MatcherFailure]]:
    """
    Get the comparison results of two requests as two list.
    The first returned list represents the matchers names that passed.
    The second list is the failed matchers as a string with failed assertion details if any.
    """
    matches_success: list[str] = []
    matches_fails: list[MatcherFailure] = []
    for m in matchers:
        matcher_name: str = getattr(m, "__name__", repr(m))
        match, assertion_message = _evaluate_matcher(m, r1, r2)
        if match:
            matches_success.append(matcher_name)
        else:
            assertion_message = get_assertion_message(assertion_message)
            matches_fails.append((matcher_name, assertion_message))
    return matches_success, matches_fails


def get_assertion_message(assertion_details: str | None) -> str | None:
    """
    Get a detailed message about the failing matcher.
    """
    return assertion_details
