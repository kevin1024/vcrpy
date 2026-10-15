import pytest

from vcr.stubs.httpx_stubs import _deserialize_response

httpx = pytest.importorskip("httpx")


def _cassette_response(message):
    """A cassette response in the current (non-legacy) format."""
    return {
        "status": {"code": 200, "message": message},
        "headers": {"Content-Type": ["text/plain"]},
        "body": {"string": b"hello"},
    }


def test_deserialize_response_keeps_the_recorded_reason_phrase():
    response = _deserialize_response(_cassette_response("Peachy"), httpx)

    assert response.status_code == 200
    assert response.reason_phrase == "Peachy"


@pytest.mark.parametrize("message", [None, ""])
def test_deserialize_response_without_a_reason_phrase(message):
    """Cassettes recorded before 8.2.0 have no reason phrase.

    The httpcore stub these cassettes were recorded with left ``extensions``
    unset in that case, so httpx derived the reason phrase from the status
    code. Passing the missing value straight through instead crashes on
    ``None`` and blanks the phrase on ``""``.
    """
    response = _deserialize_response(_cassette_response(message), httpx)

    assert response.status_code == 200
    assert response.reason_phrase == "OK"
