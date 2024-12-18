import asyncio
import functools
import inspect
import logging
from unittest.mock import MagicMock, patch

import httpx

from vcr.errors import CannotOverwriteExistingCassetteException
from vcr.filters import decode_response
from vcr.request import Request as VcrRequest
from vcr.serializers.compat import convert_body_to_bytes

_httpx_signature = inspect.signature(httpx.Client.request)

try:
    HTTPX_REDIRECT_PARAM = _httpx_signature.parameters["follow_redirects"]
except KeyError:
    HTTPX_REDIRECT_PARAM = _httpx_signature.parameters["allow_redirects"]


_logger = logging.getLogger(__name__)


def _transform_headers(httpx_response):
    """
    Some headers can appear multiple times, like "Set-Cookie".
    Therefore transform to every header key to list of values.
    """

    out = {}
    for key, var in httpx_response.headers.raw:
        decoded_key = key.decode("utf-8")
        out.setdefault(decoded_key, [])
        out[decoded_key].append(var.decode("utf-8"))
    return out


async def _to_serialized_response(resp, aread):
    # The content shouldn't already have been read in by HTTPX.
    assert not hasattr(resp, "_decoder")

    # Retrieve the content, but without decoding it.
    with patch.dict(resp.headers, {"Content-Encoding": ""}):
        if aread:
            await resp.aread()
        else:
            resp.read()

    result = {
        "status": {"code": resp.status_code, "message": resp.reason_phrase},
        "headers": _transform_headers(resp),
        "body": {"string": resp.content},
    }

    # As the content wasn't decoded, we restore the response to a state which
    # will be capable of decoding the content for the consumer.
    del resp._decoder
    resp._content = resp._get_content_decoder().decode(resp.content)
    return result


def _from_serialized_headers(headers):
    """
    httpx accepts headers as list of tuples of header key and value.
    """

    header_list = []
    for key, values in headers.items():
        for v in values:
            header_list.append((key, v))
    return header_list


@patch("httpx.Response.close", MagicMock())
@patch("httpx.Response.read", MagicMock())
def _from_serialized_response(request, serialized_response, history=None):
    # Cassette format generated for HTTPX requests by older versions of
    # vcrpy. We restructure the content to resemble what a regular
    # cassette looks like.
    if "status_code" in serialized_response:
        serialized_response = decode_response(
            convert_body_to_bytes(
                {
                    "headers": serialized_response["headers"],
                    "body": {"string": serialized_response["content"]},
                    "status": {"code": serialized_response["status_code"]},
                },
            ),
        )
        extensions = None
    else:
        extensions = {"reason_phrase": serialized_response["status"]["message"].encode()}

    response = httpx.Response(
        status_code=serialized_response["status"]["code"],
        request=request,
        headers=_from_serialized_headers(serialized_response["headers"]),
        content=serialized_response["body"]["string"],
        history=history or [],
        extensions=extensions,
    )

    return response


def _make_vcr_request(httpx_request, **kwargs):
    body = httpx_request.read().decode("utf-8")
    uri = str(httpx_request.url)
    headers = dict(httpx_request.headers)
    return VcrRequest(httpx_request.method, uri, body, headers)


def _shared_vcr_send(cassette, real_send, *args, **kwargs):
    real_request = args[1]

    vcr_request = _make_vcr_request(real_request, **kwargs)

    if cassette.can_play_response_for(vcr_request):
        return vcr_request, _play_responses(cassette, real_request, vcr_request, args[0], kwargs)

    if cassette.write_protected and cassette.filter_request(vcr_request):
        raise CannotOverwriteExistingCassetteException(cassette=cassette, failed_request=vcr_request)

    _logger.info("%s not in cassette, sending to real server", vcr_request)
    return vcr_request, None


async def _record_responses(cassette, vcr_request, real_response, aread):
    for past_real_response in real_response.history:
        past_vcr_request = _make_vcr_request(past_real_response.request)
        cassette.append(past_vcr_request, await _to_serialized_response(past_real_response, aread))

    if real_response.history:
        # If there was a redirection keep we want the request which will hold the
        # final redirect value
        vcr_request = _make_vcr_request(real_response.request)

    cassette.append(vcr_request, await _to_serialized_response(real_response, aread))
    return real_response


def _play_responses(cassette, request, vcr_request, client, kwargs):
    vcr_response = cassette.play_response(vcr_request)
    response = _from_serialized_response(request, vcr_response)
    return response


async def _async_vcr_send(cassette, real_send, *args, **kwargs):
    vcr_request, response = _shared_vcr_send(cassette, real_send, *args, **kwargs)
    if response:
        # add cookies from response to session cookie store
        args[0].cookies.extract_cookies(response)
        return response

    real_response = await real_send(*args, **kwargs)
    await _record_responses(cassette, vcr_request, real_response, aread=True)
    return real_response


def async_vcr_send(cassette, real_send):
    @functools.wraps(real_send)
    def _inner_send(*args, **kwargs):
        return _async_vcr_send(cassette, real_send, *args, **kwargs)

    return _inner_send


def _run_async_function(sync_func, *args, **kwargs):
    """
    Safely run an asynchronous function from a synchronous context.
    Handles both cases:
    - An event loop is already running.
    - No event loop exists yet.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(sync_func(*args, **kwargs))
    else:
        # If inside a running loop, create a task and wait for it
        return asyncio.ensure_future(sync_func(*args, **kwargs))


def _sync_vcr_send(cassette, real_send, *args, **kwargs):
    vcr_request, response = _shared_vcr_send(cassette, real_send, *args, **kwargs)
    if response:
        # add cookies from response to session cookie store
        args[0].cookies.extract_cookies(response)
        return response

    real_response = real_send(*args, **kwargs)
    _run_async_function(_record_responses, cassette, vcr_request, real_response, aread=False)
    return real_response


def sync_vcr_send(cassette, real_send):
    @functools.wraps(real_send)
    def _inner_send(*args, **kwargs):
        return _sync_vcr_send(cassette, real_send, *args, **kwargs)

    return _inner_send
