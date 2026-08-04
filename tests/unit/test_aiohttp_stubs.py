import pytest

aiohttp = pytest.importorskip("aiohttp")

from vcr.request import Request  # noqa: E402
from vcr.stubs.aiohttp_stubs import build_response  # noqa: E402


def test_build_response_sets_raw_headers():
    """Replayed aiohttp responses should expose ``raw_headers`` (#970)."""
    vcr_request = Request("GET", "https://example.com/", body=None, headers={"Accept": ["*/*"]})
    vcr_response = {
        "status": {"code": 200, "message": "OK"},
        "headers": {
            "Content-Type": ["text/plain"],
            "Content-Length": ["5"],
            "X-Test": ["1"],
        },
        "body": {"string": b"hello"},
    }
    response = build_response(vcr_request, vcr_response, history=[])

    assert response.raw_headers is not None
    raw = dict(response.raw_headers)
    assert raw[b"Content-Type"] == b"text/plain"
    assert raw[b"Content-Length"] == b"5"
    assert raw[b"X-Test"] == b"1"
