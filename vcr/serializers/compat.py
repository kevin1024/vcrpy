from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from ..types import RequestDict, Response, SerializedRequest, SerializedResponse

_T = TypeVar("_T")


def request_to_unicode(request: RequestDict) -> SerializedRequest:
    """A copy of a request dict for serializing, with a UTF-8 body as str."""
    return {**request, "body": _convert_string_to_unicode(request["body"])}


def response_to_unicode(response: Response) -> SerializedResponse:
    """A copy of a response for serializing, with a UTF-8 body as str."""
    match response:
        case {"body": {"string": string}}:
            return {**response, "body": {"string": _convert_string_to_unicode(string)}}
        case {"body": dict()}:
            return {**response, "body": {}}
    # Not a response. Some of the tests serialize other values, which are kept as they are.
    return response  # type: ignore[return-value]


def response_to_bytes(response: SerializedResponse) -> Response:
    """A copy of a deserialized response, with the body as bytes."""
    match response:
        case {"body": {"string": str() as string}}:
            # Sometimes the thing actually is binary, so if you can't encode it, it's kept as it is.
            with suppress(UnicodeEncodeError):
                return {**response, "body": {"string": string.encode("utf-8")}}
        case {"body": {"string": bytes() | None as string}}:
            return {**response, "body": {"string": string}}
        case {"body": dict()}:
            return {**response, "body": {}}
    # Not a response, or a body that can't be encoded. Some of the tests serialize
    # other values, which are kept as they are.
    return response  # type: ignore[return-value]


def convert_to_bytes(resp: object) -> object:
    resp = convert_body_to_bytes(resp)
    return resp


def convert_to_unicode(resp: object) -> object:
    resp = convert_body_to_unicode(resp)
    return resp


def convert_body_to_bytes(resp: object) -> object:
    """
    If the request body is a string, encode it to bytes (for python3 support)

    By default yaml serializes to utf-8 encoded bytestrings.
    When this cassette is loaded by python3, it's automatically decoded
    into unicode strings. This makes sure that it stays a bytestring, since
    that's what all the internal httplib machinery is expecting.

    For more info on py3 yaml:
    http://pyyaml.org/wiki/PyYAMLDocumentation#Python3support
    """
    match resp:
        case {"body": dict() as body}:
            match body.get("string"):
                case str() as string:
                    # Sometimes the thing actually is binary, so if you can't encode
                    # it, just give up.
                    with suppress(UnicodeEncodeError):
                        body["string"] = string.encode("utf-8")
    # Anything else isn't a response with a body. Some of the tests just
    # serialize and deserialize a string.
    return resp


def _convert_string_to_unicode(string: _T) -> str | _T:
    """
    If the string is bytes, decode it to a string (for python3 support)
    """
    match string:
        case bytes() | bytearray():
            try:
                return string.decode("utf-8")
            except UnicodeDecodeError:
                # Sometimes the string actually is binary, so if you can't decode it, just give up.
                return string
        case _:
            return string


def convert_body_to_unicode(resp: object) -> object:
    """
    If the request or responses body is bytes, decode it to a string
    (for python3 support)
    """
    if not isinstance(resp, dict):
        # Some of the tests just serialize and deserialize a string.
        return _convert_string_to_unicode(resp)
    else:
        body = resp.get("body")

        if body is not None:
            if isinstance(body, dict) and "string" in body:
                body["string"] = _convert_string_to_unicode(body["string"])
            else:
                # The thing we were converting either wasn't a dictionary or
                # didn't have the keys we were expecting.
                # For example request object has no 'string' key.
                resp["body"] = _convert_string_to_unicode(body)

    return resp
