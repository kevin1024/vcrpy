import functools
import logging
from collections import defaultdict

from httpx import ByteStream, Response
from httpx._exceptions import request_context

from vcr.errors import CannotOverwriteExistingCassetteException
from vcr.filters import decode_response
from vcr.request import Request as VcrRequest
from vcr.serializers.compat import convert_body_to_bytes

_logger = logging.getLogger(__name__)


def _serialize_headers(real_response):
    """
    Some headers can appear multiple times, like "Set-Cookie".
    Therefore serialize every header key to a list of values.
    """

    headers = defaultdict(list)

    for name, value in real_response.headers.multi_items():
        headers[name].append(value)

    return dict(headers)


def _serialize_response(real_response, real_response_content):
    return {
        "status": {"code": real_response.status_code, "message": real_response.reason_phrase},
        "headers": _serialize_headers(real_response),
        "body": {"string": real_response_content},
    }


def _deserialize_headers(headers):
    """
    httpx accepts headers as list of tuples of header key and value.
    """

    return [(name, value) for name, values in headers.items() for value in values]


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
        extensions = {"reason_phrase": vcr_response["status"]["message"].encode("ascii")}

    return Response(
        vcr_response["status"]["code"],
        headers=_deserialize_headers(vcr_response["headers"]),
        # Don't use content, because that closes the response,
        # which we do not want as the real response is unclosed
        stream=ByteStream(vcr_response["body"]["string"]),
        extensions=extensions,
    )


def _make_vcr_request(real_request, real_request_body):
    return VcrRequest(real_request.method, str(real_request.url), real_request_body, real_request.headers)


def _vcr_request(cassette, real_request, real_request_body):
    vcr_request = _make_vcr_request(real_request, real_request_body)

    if cassette.can_play_response_for(vcr_request):
        return vcr_request, _play_responses(cassette, vcr_request)

    if cassette.write_protected and cassette.filter_request(vcr_request):
        raise CannotOverwriteExistingCassetteException(cassette=cassette, failed_request=vcr_request)

    _logger.info("%s not in cassette, sending to real server", vcr_request)

    return vcr_request, None


def _record_responses(cassette, vcr_request, real_response, real_response_content):
    cassette.append(vcr_request, _serialize_response(real_response, real_response_content))


def _play_responses(cassette, vcr_request):
    vcr_response = cassette.play_response(vcr_request)
    real_response = _deserialize_response(vcr_response)

    return real_response


async def _vcr_handle_async_request(cassette, real_handle_async_request, self, real_request):
    # Reading the request stream consumes the iterator, so we need to restore it afterwards
    real_request_body = b"".join([part async for part in real_request.stream])
    real_request.stream = ByteStream(real_request_body)

    vcr_request, vcr_response = _vcr_request(cassette, real_request, real_request_body)

    if vcr_response:
        return vcr_response

    real_response = await real_handle_async_request(self, real_request)
    real_response_content = b"".join([part async for part in real_response.stream])

    # Close the original stream so that the connection is released back to the connection pool
    with request_context(request=real_response._request):
        await real_response.stream.aclose()

    # Reading the response stream consumes the iterator, so we need to restore it
    real_response.stream = ByteStream(real_response_content)

    _record_responses(cassette, vcr_request, real_response, real_response_content)

    return real_response


def vcr_handle_async_request(cassette, real_handle_async_request):
    @functools.wraps(real_handle_async_request)
    def _inner_handle_async_request(self, real_request):
        return _vcr_handle_async_request(cassette, real_handle_async_request, self, real_request)

    return _inner_handle_async_request


def _vcr_handle_request(cassette, real_handle_request, self, real_request):
    # Reading the request stream consumes the iterator, so we need to restore it afterwards
    real_request_body = b"".join(real_request.stream)
    real_request.stream = ByteStream(real_request_body)

    vcr_request, vcr_response = _vcr_request(cassette, real_request, real_request_body)

    if vcr_response:
        return vcr_response

    real_response = real_handle_request(self, real_request)
    real_response_content = b"".join(real_response.stream)

    # Close the original stream so that the connection is released back to the connection pool
    with request_context(request=real_response._request):
        real_response.stream.close()

    # Reading the response stream consumes the iterator, so we need to restore it
    real_response.stream = ByteStream(real_response_content)

    _record_responses(cassette, vcr_request, real_response, real_response_content)

    return real_response


def vcr_handle_request(cassette, real_handle_request):
    @functools.wraps(real_handle_request)
    def _inner_handle_request(self, real_request):
        return _vcr_handle_request(cassette, real_handle_request, self, real_request)

    return _inner_handle_request
