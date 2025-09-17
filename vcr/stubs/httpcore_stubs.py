import asyncio
import functools
import logging
from collections import defaultdict
from collections.abc import AsyncIterable, Iterable

from httpcore import Response
from httpcore._models import ByteStream

from vcr.errors import CannotOverwriteExistingCassetteException
from vcr.filters import decode_response
from vcr.request import Request as VcrRequest
from vcr.serializers.compat import convert_body_to_bytes

_logger = logging.getLogger(__name__)


async def _convert_byte_stream(stream):
    if isinstance(stream, Iterable):
        return list(stream)

    if isinstance(stream, AsyncIterable):
        return [part async for part in stream]

    raise TypeError(
        f"_convert_byte_stream: stream must be Iterable or AsyncIterable, got {type(stream).__name__}",
    )


def _serialize_headers(real_response):
    """
    Some headers can appear multiple times, like "Set-Cookie".
    Therefore serialize every header key to a list of values.
    """

    headers = defaultdict(list)

    for name, value in real_response.headers:
        headers[name.decode("ascii")].append(value.decode("ascii"))

    return dict(headers)


async def _serialize_response(real_response):
    # The reason_phrase may not exist
    try:
        reason_phrase = real_response.extensions["reason_phrase"].decode("ascii")
    except KeyError:
        reason_phrase = None

    # Reading the response stream consumes the iterator, so we need to restore it afterwards
    content = b"".join(await _convert_byte_stream(real_response.stream))
    real_response.stream = ByteStream(content)

    return {
        "status": {"code": real_response.status, "message": reason_phrase},
        "headers": _serialize_headers(real_response),
        "body": {"string": content},
    }


def _deserialize_headers(headers):
    """
    httpcore accepts headers as list of tuples of header key and value.
    """

    return [
        (name.encode("ascii"), value.encode("ascii")) for name, values in headers.items() for value in values
    ]


def _deserialize_response(vcr_response):
    # Cassette format generated for HTTPX requests by older versions of
    # vcrpy. We restructure the content to resemble what a regular
    # cassette looks like.
    if "status_code" in vcr_response:
        vcr_response = decode_response(
            convert_body_to_bytes(
                {
                    "headers": vcr_response["headers"],
                    "body": {"string": vcr_response["content"]},
                    "status": {"code": vcr_response["status_code"]},
                },
            ),
        )
        extensions = None
    else:
        extensions = (
            {"reason_phrase": vcr_response["status"]["message"].encode("ascii")}
            if vcr_response["status"]["message"]
            else None
        )

    return Response(
        vcr_response["status"]["code"],
        headers=_deserialize_headers(vcr_response["headers"]),
        content=vcr_response["body"]["string"],
        extensions=extensions,
    )


async def _make_vcr_request(real_request):
    # Reading the request stream consumes the iterator, so we need to restore it afterwards
    body = b"".join(await _convert_byte_stream(real_request.stream))
    real_request.stream = ByteStream(body)

    uri = bytes(real_request.url).decode("ascii")

    # As per HTTPX: If there are multiple headers with the same key, then we concatenate them with commas
    headers = defaultdict(list)

    for name, value in real_request.headers:
        headers[name.decode("ascii")].append(value.decode("ascii"))

    headers = {name: ", ".join(values) for name, values in headers.items()}

    return VcrRequest(real_request.method.decode("ascii"), uri, body, headers)


async def _vcr_request(cassette, real_request):
    vcr_request = await _make_vcr_request(real_request)

    if cassette.can_play_response_for(vcr_request):
        return vcr_request, _play_responses(cassette, vcr_request)

    if cassette.write_protected and cassette.filter_request(vcr_request):
        raise CannotOverwriteExistingCassetteException(
            cassette=cassette,
            failed_request=vcr_request,
        )

    _logger.info("%s not in cassette, sending to real server", vcr_request)

    return vcr_request, None


async def _record_responses(cassette, vcr_request, real_response):
    cassette.append(vcr_request, await _serialize_response(real_response))


def _play_responses(cassette, vcr_request):
    vcr_response = cassette.play_response(vcr_request)
    real_response = _deserialize_response(vcr_response)

    return real_response


async def _vcr_handle_async_request(
    cassette,
    real_handle_async_request,
    self,
    real_request,
):
    vcr_request, vcr_response = await _vcr_request(cassette, real_request)

    if vcr_response:
        return vcr_response

    real_response = await real_handle_async_request(self, real_request)
    await _record_responses(cassette, vcr_request, real_response)

    return real_response


def vcr_handle_async_request(cassette, real_handle_async_request):
    @functools.wraps(real_handle_async_request)
    def _inner_handle_async_request(self, real_request):
        return _vcr_handle_async_request(
            cassette,
            real_handle_async_request,
            self,
            real_request,
        )

    return _inner_handle_async_request


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


def _vcr_handle_request(cassette, real_handle_request, self, real_request):
    vcr_request, vcr_response = _run_async_function(
        _vcr_request,
        cassette,
        real_request,
    )

    if vcr_response:
        return vcr_response

    real_response = real_handle_request(self, real_request)
    _run_async_function(_record_responses, cassette, vcr_request, real_response)

    return real_response


def vcr_handle_request(cassette, real_handle_request):
    @functools.wraps(real_handle_request)
    def _inner_handle_request(self, real_request):
        return _vcr_handle_request(cassette, real_handle_request, self, real_request)

    return _inner_handle_request
