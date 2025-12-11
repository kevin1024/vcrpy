"""Stubs for aiobotocore HTTP clients.

aiobotocore uses aiohttp under the hood but wraps responses in AioAWSResponse.
This module patches AIOHTTPSession.send to intercept requests and play back
recorded responses from VCR cassettes.
"""

import asyncio
import functools
import logging

from vcr.errors import CannotOverwriteExistingCassetteException
from vcr.request import Request

log = logging.getLogger(__name__)


def _serialize_headers(headers):
    """Serialize headers dict to VCR format (dict with list values)."""
    serialized = {}
    for k, v in headers.items():
        key = str(k)
        if key not in serialized:
            serialized[key] = []
        serialized[key].append(str(v))
    return serialized


def _deserialize_headers(headers):
    """Deserialize VCR headers format to a simple dict (first value only).

    botocore expects headers as {str: str}, not {str: list[str]}.
    """
    deserialized = {}
    for k, vs in headers.items():
        if isinstance(vs, list):
            deserialized[k.lower()] = vs[0] if vs else ""
        else:
            deserialized[k.lower()] = vs
    return deserialized


class MockAioHTTPResponse:
    """Mock aiohttp response for playback.

    This mimics the interface that aiobotocore expects from aiohttp.ClientResponse,
    specifically the raw_headers property and read() method.
    """

    def __init__(self, status, headers, body, url):
        self.status = status
        self._headers = headers
        self._body = body
        self.url = url
        self._read = False

    @property
    def raw_headers(self):
        """Return headers as list of (bytes, bytes) tuples.

        aiobotocore accesses raw_headers to convert to lowercase dict.
        """
        return [(k.encode("utf-8"), v.encode("utf-8")) for k, v in self._headers.items()]

    async def read(self):
        """Read the response body."""
        self._read = True
        return self._body

    def release(self):
        """Release the response (no-op for mock)."""
        pass


class MockAioAWSResponse:
    """Mock AioAWSResponse for playback.

    This mimics the interface of aiobotocore.awsrequest.AioAWSResponse.
    """

    def __init__(self, url, status_code, headers, raw):
        self.url = url
        self.status_code = status_code
        self.headers = headers
        self.raw = raw
        self._content = None

    async def _content_prop(self):
        """Content of the response as bytes."""
        if self._content is None:
            self._content = await self.raw.read() or b""
        return self._content

    @property
    def content(self):
        return self._content_prop()


def _build_vcr_request(request):
    """Build a VCR Request from a botocore AWSRequest."""
    body = request.body
    if isinstance(body, bytes):
        pass
    elif hasattr(body, "read"):
        body = body.read()
        if hasattr(request.body, "seek"):
            request.body.seek(0)
    elif body is None:
        body = b""
    else:
        body = str(body).encode("utf-8")

    headers = _serialize_headers(request.headers)
    return Request(request.method, request.url, body, headers)


def _build_response(vcr_response, url):
    """Build a mock AioAWSResponse from VCR response data."""
    status_code = vcr_response["status"]["code"]
    headers = _deserialize_headers(vcr_response["headers"])
    body = vcr_response["body"].get("string", b"")
    if isinstance(body, str):
        body = body.encode("utf-8")

    # Create a mock aiohttp response that aiobotocore expects
    mock_aiohttp_response = MockAioHTTPResponse(
        status=status_code,
        headers=headers,
        body=body,
        url=url,
    )

    return MockAioAWSResponse(
        url=url,
        status_code=status_code,
        headers=headers,
        raw=mock_aiohttp_response,
    )


async def record_response(cassette, vcr_request, response):
    """Record a VCR request-response pair to the cassette."""
    try:
        body_content = await response.content
        body = {"string": body_content}
    except Exception:
        body = {}

    vcr_response = {
        "status": {"code": response.status_code, "message": ""},
        "headers": _serialize_headers(response.headers),
        "body": body,
    }

    cassette.append(vcr_request, vcr_response)


def vcr_send(cassette, real_send):
    """Create a patched send method for AIOHTTPSession.

    This intercepts HTTP requests made by aiobotocore and either:
    - Plays back a recorded response if one matches in the cassette
    - Records the real response if in recording mode
    - Raises an error if the cassette is write-protected and no match exists
    """

    @functools.wraps(real_send)
    async def new_send(self, request):
        vcr_request = _build_vcr_request(request)

        if cassette.can_play_response_for(vcr_request):
            log.info("Playing response for %s from cassette", vcr_request)
            vcr_response = cassette.play_response(vcr_request)
            return _build_response(vcr_response, request.url)

        if cassette.write_protected and cassette.filter_request(vcr_request):
            raise CannotOverwriteExistingCassetteException(
                cassette=cassette, failed_request=vcr_request
            )

        log.info("%s not in cassette, sending to real server", vcr_request)

        response = await real_send(self, request)

        # Record the response
        await record_response(cassette, vcr_request, response)

        return response

    return new_send
