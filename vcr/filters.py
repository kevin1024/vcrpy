import copy
import json
import zlib
from io import BytesIO
from urllib.parse import unquote_plus, urlencode, urlparse, urlunparse

from .util import CaseInsensitiveDict

try:
    # This supports both brotli & brotlipy packages
    import brotli
except ImportError:
    try:
        import brotlicffi as brotli
    except ImportError:
        brotli = None


def decompress_deflate(body):
    try:
        return zlib.decompress(body)
    except zlib.error:
        # Assume the response was already decompressed
        return body


def decompress_gzip(body):
    # To (de-)compress gzip format, use wbits = zlib.MAX_WBITS | 16.
    try:
        return zlib.decompress(body, zlib.MAX_WBITS | 16)
    except zlib.error:
        # Assume the response was already decompressed
        return body


AVAILABLE_DECOMPRESSORS = {
    "deflate": decompress_deflate,
    "gzip": decompress_gzip,
}

if brotli is not None:

    def decompress_brotli(body):
        try:
            return brotli.decompress(body)
        except brotli.error:
            # Assume the response was already decompressed
            return body

    AVAILABLE_DECOMPRESSORS["br"] = decompress_brotli


def replace_text(obj, text, replacement):
    """Return a copy of obj with every occurrence of text replaced by replacement.

    Replaces in strings and bytes (encoded as UTF-8), and in the keys and
    values of dicts and the items of lists and tuples, at any depth.
    Anything else is returned unchanged.
    """
    if isinstance(obj, str):
        return obj.replace(text, replacement)
    if isinstance(obj, (bytes, bytearray)):
        return bytes(obj).replace(text.encode("utf-8"), replacement.encode("utf-8"))
    if isinstance(obj, BytesIO):
        return BytesIO(replace_text(obj.getvalue(), text, replacement))
    if isinstance(obj, dict):
        return {
            replace_text(key, text, replacement): replace_text(value, text, replacement)
            for key, value in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return type(obj)(replace_text(item, text, replacement) for item in obj)
    return obj


def sensitive_data_hooks(sensitive_data):
    """Build the interaction hooks that implement ``filter_sensitive_data``.

    ``sensitive_data`` maps placeholders to the values they stand for, as a
    dict or as (placeholder, value) pairs. A value can be a function of the
    interaction's request and response. Returns ``(hide, restore)``: ``hide``
    replaces values with their placeholders, for ``before_save_interaction``,
    and ``restore`` puts the values back, for ``after_load_interaction``.
    """
    if isinstance(sensitive_data, dict):
        sensitive_data = sensitive_data.items()
    sensitive_data = list(sensitive_data)

    def replace(request, response, restore):
        for placeholder, value in sensitive_data:
            if callable(value):
                value = value(request, response)
            if value is None:
                continue
            # Non-string values, like a port number, are matched as text.
            placeholder, value = str(placeholder), str(value)
            if not placeholder or not value:
                continue
            text, replacement = (placeholder, value) if restore else (value, placeholder)
            request = type(request)._from_dict(replace_text(request._to_dict(), text, replacement))
            response = replace_text(response, text, replacement)
        return request, response

    def hide(request, response):
        return replace(request, response, restore=False)

    def restore(request, response):
        return replace(request, response, restore=True)

    return hide, restore


def replace_headers(request, replacements):
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
            if callable(rv):
                rv = rv(key=k, value=ov, request=request)
            if rv is not None:
                new_headers[k] = rv
    request.headers = new_headers
    return request


def remove_headers(request, headers_to_remove):
    """
    Wrap replace_headers() for API backward compatibility.
    """
    replacements = [(k, None) for k in headers_to_remove]
    return replace_headers(request, replacements)


def replace_query_parameters(request, replacements):
    """Replace query parameters in request according to replacements.

    The replacements should be a list of (key, value) pairs where the value can be any of:
      1. A simple replacement string value.
      2. None to remove the given header.
      3. A callable which accepts (key, value, request) and returns a string
         value or None.
    """
    query = request.query
    new_query = []
    replacements = dict(replacements)
    for k, ov in query:
        if k not in replacements:
            new_query.append((k, ov))
        else:
            rv = replacements[k]
            if callable(rv):
                rv = rv(key=k, value=ov, request=request)
            if rv is not None:
                new_query.append((k, rv))
    uri_parts = list(urlparse(request.uri))
    uri_parts[4] = urlencode(new_query)
    request.uri = urlunparse(uri_parts)
    return request


def remove_query_parameters(request, query_parameters_to_remove):
    """
    Wrap replace_query_parameters() for API backward compatibility.
    """
    replacements = [(k, None) for k in query_parameters_to_remove]
    return replace_query_parameters(request, replacements)


def _replace_urlencoded_parameters(body, replacements, request):
    """Replace parameters in a urlencoded form data body.

    Raises UnicodeError if the body (or one of its keys/values) can not be
    decoded as UTF-8, in which case it is not urlencoded form data.
    """
    splits = [p.partition(b"=") for p in body.split(b"&")]
    new_splits = []
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
                if callable(rv):
                    rv = rv(key=rk, value=ov.decode("utf-8"), request=request)
                if rv is not None:
                    new_splits.append((k, sep, rv.encode("utf-8")))
    return b"&".join(k if not sep else b"".join([k, sep, v]) for k, sep, v in new_splits)


def _replace_nested_parameters(data, replacements, request):
    """Return a copy of data with replacements applied to the keys of dicts at any depth, in lists too."""
    if isinstance(data, dict):
        new_data = {}
        for k, ov in data.items():
            if k not in replacements:
                new_data[k] = _replace_nested_parameters(ov, replacements, request)
                continue
            rv = replacements[k]
            if callable(rv):
                rv = rv(key=k, value=ov, request=request)
            if rv is not None:
                new_data[k] = rv
        return new_data
    if isinstance(data, list):
        return [_replace_nested_parameters(item, replacements, request) for item in data]
    return data


def replace_body_parameters(request, replacements, recursive=False):
    """Replace body parameters in request--either form data or json--according to replacements.

    The replacements should be a list of (key, value) pairs where the value can be any of:
      1. A simple replacement string value.
      2. None to remove the given header.
      3. A callable which accepts (key, value, request) and returns a string
         value or None.

    If recursive is true, keys are also replaced in objects nested in JSON
    and dict bodies, including objects in lists.
    """
    if not request.body:
        # Nothing to replace
        return request

    if isinstance(request.body, BytesIO):
        return request

    replacements = dict(replacements)
    if recursive and isinstance(request.body, dict):
        request.body = _replace_nested_parameters(request.body, replacements, request)
    elif recursive and request.headers.get("Content-Type") == "application/json":
        json_data = _replace_nested_parameters(json.loads(request.body), replacements, request)
        request.body = json.dumps(json_data).encode("utf-8")
    elif isinstance(request.body, dict):
        new_body = request.body.copy()
        for k, rv in replacements.items():
            if k in new_body:
                ov = new_body.pop(k)
                if callable(rv):
                    rv = rv(key=k, value=ov, request=request)
                if rv is not None:
                    new_body[k] = rv
        request.body = new_body
    elif request.headers.get("Content-Type") == "application/json":
        json_data = json.loads(request.body)
        for k, rv in replacements.items():
            if k in json_data:
                ov = json_data.pop(k)
                if callable(rv):
                    rv = rv(key=k, value=ov, request=request)
                if rv is not None:
                    json_data[k] = rv
        request.body = json.dumps(json_data).encode("utf-8")
    else:
        try:
            body = request.body.encode("utf-8") if isinstance(request.body, str) else request.body
            request.body = _replace_urlencoded_parameters(body, replacements, request)
        except UnicodeError:
            # The body isn't UTF-8 encoded text -- e.g. a binary file
            # upload -- so it can't be urlencoded form data and there is
            # nothing we can safely replace. Leave it untouched instead of
            # blowing up while recording/replaying (#660).
            pass
    return request


def replace_post_data_parameters(request, replacements, recursive=False):
    """
    Wrap replace_body_parameters() for API backward compatibility: only filters POST requests.
    """
    if request.method != "POST":
        return request

    return replace_body_parameters(request, replacements, recursive=recursive)


def remove_post_data_parameters(request, post_data_parameters_to_remove):
    """
    Wrap replace_post_data_parameters() for API backward compatibility.
    """
    replacements = [(k, None) for k in post_data_parameters_to_remove]
    return replace_post_data_parameters(request, replacements)


def decode_response(response):
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
    if not decompressor:
        return response

    headers["content-encoding"].remove(content_encoding[0])
    if not headers["content-encoding"]:
        del headers["content-encoding"]

    new_body = decompressor(response["body"]["string"])
    response["body"]["string"] = new_body
    headers["content-length"] = [str(len(new_body))]
    response["headers"] = dict(headers)
    return response
