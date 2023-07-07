import json
import logging
import urllib
import xmlrpc.client
from string import hexdigits

from .util import read_body

_HEXDIG_CODE_POINTS: set[int] = {ord(s.encode("ascii")) for s in hexdigits}

log = logging.getLogger(__name__)


def method(r1, r2):
    if r1.method != r2.method:
        raise AssertionError(f"{r1.method} != {r2.method}")


def uri(r1, r2):
    if r1.uri != r2.uri:
        raise AssertionError(f"{r1.uri} != {r2.uri}")


def host(r1, r2):
    if r1.host != r2.host:
        raise AssertionError(f"{r1.host} != {r2.host}")


def scheme(r1, r2):
    if r1.scheme != r2.scheme:
        raise AssertionError(f"{r1.scheme} != {r2.scheme}")


def port(r1, r2):
    if r1.port != r2.port:
        raise AssertionError(f"{r1.port} != {r2.port}")


def path(r1, r2):
    if r1.path != r2.path:
        raise AssertionError(f"{r1.path} != {r2.path}")


def query(r1, r2):
    if r1.query != r2.query:
        raise AssertionError(f"{r1.query} != {r2.query}")


def raw_body(r1, r2):
    if read_body(r1) != read_body(r2):
        raise AssertionError


def body(r1, r2):
    transformers = list(_get_transformers(r1))
    if transformers != list(_get_transformers(r2)):
        transformers = []

    b1 = read_body(r1)
    b2 = read_body(r2)
    for transform in transformers:
        b1 = transform(b1)
        b2 = transform(b2)

    if b1 != b2:
        raise AssertionError


def headers(r1, r2):
    if r1.headers != r2.headers:
        raise AssertionError(f"{r1.headers} != {r2.headers}")


def _header_checker(value, header="Content-Type"):
    def checker(headers):
        _header = headers.get(header, "")
        if isinstance(_header, bytes):
            _header = _header.decode("utf-8")
        return value in _header.lower()

    return checker


def _dechunk(body):
    if isinstance(body, str):
        body = body.encode("utf-8")
    elif isinstance(body, bytearray):
        body = bytes(body)
    elif hasattr(body, "__iter__"):
        body = list(body)
        if body:
            if isinstance(body[0], str):
                body = ("".join(body)).encode("utf-8")
            elif isinstance(body[0], bytes):
                body = b"".join(body)
            elif isinstance(body[0], int):
                body = bytes(body)
            else:
                raise ValueError(f"Body chunk type {type(body[0])} not supported")
        else:
            body = None

    if not isinstance(body, bytes):
        return body

    # Now decode chunked data format (https://en.wikipedia.org/wiki/Chunked_transfer_encoding)
    # Example input: b"45\r\n<69 bytes>\r\n0\r\n\r\n" where int(b"45", 16) == 69.
    CHUNK_GAP = b"\r\n"
    BODY_LEN: int = len(body)

    chunks: list[bytes] = []
    pos: int = 0

    while True:
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


def _transform_json(body):
    if body:
        return json.loads(body)


_xml_header_checker = _header_checker("text/xml")
_xmlrpc_header_checker = _header_checker("xmlrpc", header="User-Agent")
_checker_transformer_pairs = (
    (_header_checker("chunked", header="Transfer-Encoding"), _dechunk),
    (
        _header_checker("application/x-www-form-urlencoded"),
        lambda body: urllib.parse.parse_qs(body.decode("ascii")),
    ),
    (_header_checker("application/json"), _transform_json),
    (lambda request: _xml_header_checker(request) and _xmlrpc_header_checker(request), xmlrpc.client.loads),
)


def _get_transformers(request):
    for checker, transformer in _checker_transformer_pairs:
        if checker(request.headers):
            yield transformer


def requests_match(r1, r2, matchers):
    successes, failures = get_matchers_results(r1, r2, matchers)
    if failures:
        log.debug(f"Requests {r1} and {r2} differ.\nFailure details:\n{failures}")
    return len(failures) == 0


def _evaluate_matcher(matcher_function, *args):
    """
    Evaluate the result of a given matcher as a boolean with an assertion error message if any.
    It handles two types of matcher :
    - a matcher returning a boolean value.
    - a matcher that only makes an assert, returning None or raises an assertion error.
    """
    assertion_message = None
    try:
        match = matcher_function(*args)
        match = True if match is None else match
    except AssertionError as e:
        match = False
        assertion_message = str(e)
    return match, assertion_message


def get_matchers_results(r1, r2, matchers):
    """
    Get the comparison results of two requests as two list.
    The first returned list represents the matchers names that passed.
    The second list is the failed matchers as a string with failed assertion details if any.
    """
    matches_success, matches_fails = [], []
    for m in matchers:
        matcher_name = m.__name__
        match, assertion_message = _evaluate_matcher(m, r1, r2)
        if match:
            matches_success.append(matcher_name)
        else:
            assertion_message = get_assertion_message(assertion_message)
            matches_fails.append((matcher_name, assertion_message))
    return matches_success, matches_fails


def get_assertion_message(assertion_details):
    """
    Get a detailed message about the failing matcher.
    """
    return assertion_details
