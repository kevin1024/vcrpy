from __future__ import annotations

import contextlib
import copy
import importlib
import json
import re
import zlib
from collections.abc import Callable, Iterable, Mapping
from io import BytesIO
from types import ModuleType
from typing import TYPE_CHECKING, TypeVar
from urllib.parse import unquote_plus, urlencode, urlparse, urlunparse

from .util import CaseInsensitiveDict

if TYPE_CHECKING:
    from .request import Request
    from .types import JSON, Interaction, Replacement, Response, SensitiveData

_T = TypeVar("_T")


def decompress_deflate(body: bytes) -> bytes:
    try:
        return zlib.decompress(body)
    except zlib.error:
        # Assume the response was already decompressed
        return body


def decompress_gzip(body: bytes) -> bytes:
    # To (de-)compress gzip format, use wbits = zlib.MAX_WBITS | 16.
    try:
        return zlib.decompress(body, zlib.MAX_WBITS | 16)
    except zlib.error:
        # Assume the response was already decompressed
        return body


AVAILABLE_DECOMPRESSORS: dict[str, Callable[[bytes], bytes]] = {
    "deflate": decompress_deflate,
    "gzip": decompress_gzip,
}


def _import_brotli() -> ModuleType | None:
    # This supports both brotli & brotlipy packages, which needn't be installed.
    for name in ("brotli", "brotlicffi"):
        try:
            return importlib.import_module(name)
        except ImportError:
            continue
    return None


brotli: ModuleType | None = _import_brotli()


def _brotli_decompressor(module: ModuleType) -> Callable[[bytes], bytes]:
    decompress: Callable[[bytes], bytes] = module.decompress
    error: type[Exception] = module.error

    def decompress_brotli(body: bytes) -> bytes:
        try:
            return decompress(body)
        except error:
            # Assume the response was already decompressed
            return body

    return decompress_brotli


if brotli is not None:
    decompress_brotli: Callable[[bytes], bytes] = _brotli_decompressor(brotli)
    AVAILABLE_DECOMPRESSORS["br"] = decompress_brotli


def replace_text(obj: _T, text: str, replacement: str) -> _T:
    """Return a copy of obj with every occurrence of text replaced by replacement.

    Replaces in strings and bytes (encoded as UTF-8), and in the keys and
    values of dicts and the items of lists and tuples, at any depth.
    Anything else is returned unchanged. The copy has the type of obj.
    """
    match obj:
        case str():
            return type(obj)(obj.replace(text, replacement))
        case bytes() | bytearray():
            return type(obj)(obj.replace(text.encode("utf-8"), replacement.encode("utf-8")))
        case BytesIO():
            return type(obj)(replace_text(obj.getvalue(), text, replacement))
        case dict():
            new = copy.copy(obj)
            new.clear()
            for key, value in obj.items():
                new[replace_text(key, text, replacement)] = replace_text(value, text, replacement)
            return new
        case list() | tuple():
            return type(obj)(replace_text(item, text, replacement) for item in obj)
        case _:
            return obj


def sensitive_data_hooks(
    sensitive_data: SensitiveData,
) -> tuple[Callable[[Request, Response], Interaction], Callable[[Request, Response], Interaction]]:
    """Build the interaction hooks that implement ``filter_sensitive_data``.

    ``sensitive_data`` maps placeholders to the values they stand for, as a
    dict or as (placeholder, value) pairs. A value can be a function of the
    interaction's request and response. Returns ``(hide, restore)``: ``hide``
    replaces values with their placeholders, for ``before_save_interaction``,
    and ``restore`` puts the values back, for ``after_load_interaction``.
    """
    pairs = list(sensitive_data.items() if isinstance(sensitive_data, Mapping) else sensitive_data)

    def replace(request: Request, response: Response, restore: bool) -> Interaction:
        for placeholder, value in pairs:
            if callable(value):
                value = value(request, response)
            if value is None:
                continue
            # Non-string values, like a port number, are matched as text.
            placeholder_text, value_text = str(placeholder), str(value)
            if not placeholder_text or not value_text:
                continue
            text, replacement = (placeholder_text, value_text) if restore else (value_text, placeholder_text)
            request = type(request)._from_dict(replace_text(request._to_dict(), text, replacement))
            response = replace_text(response, text, replacement)
        return request, response

    def hide(request: Request, response: Response) -> Interaction:
        return replace(request, response, restore=False)

    def restore(request: Request, response: Response) -> Interaction:
        return replace(request, response, restore=True)

    return hide, restore


def replace_headers(
    request: Request,
    replacements: Iterable[tuple[str, Replacement[str | bytes]]],
) -> Request:
    """Replace headers in request according to replacements.
    The replacements should be a list of (key, value) pairs where the value can be any of:
    1. A simple replacement string value.
    2. None to remove the given header.
    3. A callable which accepts (key, value, request) and returns a string value or None.
    """
    new_headers = request.headers.copy()
    for k, rv in replacements:
        if k in new_headers:
            ov = new_headers.pop(k)
            new_value = rv(key=k, value=ov, request=request) if callable(rv) else rv
            if new_value is not None:
                new_headers[k] = new_value
    request.headers = new_headers
    return request


def remove_headers(request: Request, headers_to_remove: Iterable[str]) -> Request:
    """
    Wrap replace_headers() for API backward compatibility.
    """
    replacements: list[tuple[str, Replacement[str | bytes]]] = [(k, None) for k in headers_to_remove]
    return replace_headers(request, replacements)


def replace_query_parameters(
    request: Request,
    replacements: Iterable[tuple[str, Replacement[str]]],
) -> Request:
    """Replace query parameters in request according to replacements.

    The replacements should be a list of (key, value) pairs where the value can be any of:
      1. A simple replacement string value.
      2. None to remove the given header.
      3. A callable which accepts (key, value, request) and returns a string
         value or None.
    """
    query = request.query
    new_query: list[tuple[str, str]] = []
    replacement_for = dict(replacements)
    for k, ov in query:
        if k not in replacement_for:
            new_query.append((k, ov))
        else:
            rv = replacement_for[k]
            new_value = rv(key=k, value=ov, request=request) if callable(rv) else rv
            if new_value is not None:
                new_query.append((k, new_value))
    uri_parts = list(urlparse(request.uri))
    uri_parts[4] = urlencode(new_query)
    request.uri = urlunparse(uri_parts)
    return request


def remove_query_parameters(request: Request, query_parameters_to_remove: Iterable[str]) -> Request:
    """
    Wrap replace_query_parameters() for API backward compatibility.
    """
    replacements: list[tuple[str, Replacement[str]]] = [(k, None) for k in query_parameters_to_remove]
    return replace_query_parameters(request, replacements)


def _replace_urlencoded_parameters(
    body: bytes,
    replacements: Mapping[str, Replacement[object]],
    request: Request,
) -> bytes:
    """Replace parameters in a urlencoded form data body.

    Raises UnicodeError if the body (or one of its keys/values) can not be
    decoded as UTF-8, in which case it is not urlencoded form data.
    """
    splits = [p.partition(b"=") for p in body.split(b"&")]
    new_splits: list[tuple[bytes, bytes, bytes]] = []
    for k, sep, ov in splits:
        if not sep:
            # no "=" in this segment, so it is not a key/value pair
            new_splits.append((k, sep, ov))
        else:
            rk = k.decode("utf-8")
            if rk not in replacements:
                # Parameter names are urlencoded too, e.g. "api:key" is sent as "api%3Akey"
                rk = unquote_plus(rk)
            if rk not in replacements:
                new_splits.append((k, sep, ov))
            else:
                rv = replacements[rk]
                new_value = rv(key=rk, value=ov.decode("utf-8"), request=request) if callable(rv) else rv
                if new_value is not None:
                    new_splits.append((k, sep, new_value.encode("utf-8")))
    return b"&".join(k if not sep else b"".join([k, sep, v]) for k, sep, v in new_splits)


def _replace_nested_dict(
    data: dict[str, object],
    replacements: Mapping[str, Replacement[object]],
    request: Request,
) -> dict[str, object]:
    """Return a copy of data with replacements applied to the keys of dicts at any depth, in lists too."""
    new_data: dict[str, object] = {}
    for k, ov in data.items():
        if k not in replacements:
            new_data[k] = _replace_nested_parameters(ov, replacements, request)
            continue
        rv = replacements[k]
        new_value = rv(key=k, value=ov, request=request) if callable(rv) else rv
        if new_value is not None:
            new_data[k] = new_value
    return new_data


def _replace_nested_parameters(
    data: object,
    replacements: Mapping[str, Replacement[object]],
    request: Request,
) -> object:
    if isinstance(data, dict):
        return _replace_nested_dict(data, replacements, request)
    if isinstance(data, list):
        return [_replace_nested_parameters(item, replacements, request) for item in data]
    return data


def _multipart_boundary(content_type: str | bytes | None) -> bytes | None:
    """The boundary of a multipart/form-data Content-Type, or None."""
    if isinstance(content_type, bytes):
        content_type = content_type.decode("latin-1")
    if not content_type or not content_type.lower().startswith("multipart/form-data"):
        return None
    match = re.search(r'boundary="?([^";]+)"?', content_type, re.IGNORECASE)
    return match.group(1).encode("utf-8") if match else None


def _replace_multipart_parameters(
    body: bytes,
    boundary: bytes,
    replacements: Mapping[str, Replacement[object]],
    request: Request,
) -> bytes:
    """Replace the content of form fields in a multipart/form-data body (#521).

    A field that's removed is left out of the body.
    """
    delimiter = b"--" + boundary
    preamble, *parts = body.split(delimiter)
    new_parts = []
    for part in parts:
        headers, separator, content = part.partition(b"\r\n\r\n")
        name = re.search(rb';\s*name="([^"]*)"', headers)
        key = name.group(1).decode("utf-8", "replace") if name else None
        if not separator or key is None or key not in replacements:
            new_parts.append(part)
            continue
        # The content ends before the CRLF that precedes the next delimiter.
        value, ending = (content[:-2], content[-2:]) if content.endswith(b"\r\n") else (content, b"")
        rv = replacements[key]
        if callable(rv):
            ov: str | bytes
            try:
                ov = value.decode("utf-8")
            except UnicodeDecodeError:
                ov = value
            new_value = rv(key=key, value=ov, request=request)
        else:
            new_value = rv
        if new_value is None:
            continue
        # Untyped callers' functions may return bytes, which are used as they are.
        new_content = new_value.encode("utf-8") if isinstance(new_value, str) else new_value
        new_parts.append(headers + separator + new_content + ending)
    return delimiter.join([preamble, *new_parts])


def _replace_json_parameters(
    body: bytes | bytearray,
    replacements: Mapping[str, Replacement[object]],
    request: Request,
    recursive: bool,
) -> bytes:
    json_data: JSON = json.loads(body)
    if recursive:
        return json.dumps(_replace_nested_parameters(json_data, replacements, request)).encode("utf-8")
    if isinstance(json_data, dict):
        for k, rv in replacements.items():
            if k in json_data:
                ov = json_data.pop(k)
                new_value = rv(key=k, value=ov, request=request) if callable(rv) else rv
                if new_value is not None:
                    json_data[k] = new_value
    return json.dumps(json_data).encode("utf-8")


def replace_body_parameters(
    request: Request,
    replacements: Iterable[tuple[str, Replacement[object]]],
    recursive: bool = False,
) -> Request:
    """Replace body parameters in request--either form data or json--according to replacements.

    The replacements should be a list of (key, value) pairs where the value can be any of:
      1. A simple replacement string value.
      2. None to remove the given header.
      3. A callable which accepts (key, value, request) and returns a string
         value or None.

    If recursive is true, keys are also replaced in objects nested in JSON
    and dict bodies, including objects in lists.
    """
    body = request.body
    if not body:
        # Nothing to replace
        return request

    if not isinstance(body, (bytes, bytearray, dict)):
        # A file or iterator body, e.g. a streaming upload, isn't filtered (#814).
        return request

    replacement_for = dict(replacements)
    content_type = request.headers.get("Content-Type")
    if isinstance(body, dict):
        if recursive:
            request.body = _replace_nested_dict(body, replacement_for, request)
        else:
            new_body = body.copy()
            for k, rv in replacement_for.items():
                if k in new_body:
                    ov = new_body.pop(k)
                    new_value = rv(key=k, value=ov, request=request) if callable(rv) else rv
                    if new_value is not None:
                        new_body[k] = new_value
            request.body = new_body
    elif content_type == "application/json":
        request.body = _replace_json_parameters(body, replacement_for, request, recursive)
    elif boundary := _multipart_boundary(content_type):
        request.body = _replace_multipart_parameters(bytes(body), boundary, replacement_for, request)
    else:
        # A body that isn't UTF-8 encoded text -- e.g. a binary file upload --
        # can't be urlencoded form data, and there is nothing we can safely
        # replace. Leave it untouched instead of blowing up while
        # recording/replaying (#660).
        with contextlib.suppress(UnicodeError):
            request.body = _replace_urlencoded_parameters(bytes(body), replacement_for, request)
    return request


def replace_post_data_parameters(
    request: Request,
    replacements: Iterable[tuple[str, Replacement[object]]],
    recursive: bool = False,
) -> Request:
    """
    Wrap replace_body_parameters() for API backward compatibility: only filters POST requests.
    """
    if request.method != "POST":
        return request

    return replace_body_parameters(request, replacements, recursive=recursive)


def remove_post_data_parameters(request: Request, post_data_parameters_to_remove: Iterable[str]) -> Request:
    """
    Wrap replace_post_data_parameters() for API backward compatibility.
    """
    replacements: list[tuple[str, Replacement[object]]] = [(k, None) for k in post_data_parameters_to_remove]
    return replace_post_data_parameters(request, replacements)


def decode_response(response: Response) -> Response:
    """
    If the response is compressed with any supported compression (gzip,
    deflate, br if available):
      1. decompress the response body
      2. delete the content-encoding header
      3. update content-length header to decompressed length
    """

    # Deepcopy here in case `headers` contain objects that could
    # be mutated by a shallow copy and corrupt the real response.
    response = copy.deepcopy(response)
    headers = CaseInsensitiveDict(response["headers"])
    content_encoding = headers.get("content-encoding")
    if not content_encoding:
        return response
    decompressor = AVAILABLE_DECOMPRESSORS.get(content_encoding[0])
    body = response["body"].get("string")
    if not decompressor or body is None:
        # A response without a body, like one to a HEAD request, has nothing to decompress.
        return response

    headers["content-encoding"].remove(content_encoding[0])
    if not headers["content-encoding"]:
        del headers["content-encoding"]

    new_body = decompressor(body)
    response["body"]["string"] = new_body
    headers["content-length"] = [str(len(new_body))]
    response["headers"] = dict(headers)
    return response
