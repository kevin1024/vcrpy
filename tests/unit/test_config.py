import tempfile

from vcr.config import VCR
from vcr.request import Request


def _build_before_record_request(**options):
    return VCR(**options)._build_before_record_request(options)


def test_before_record_request_does_not_mutate_original():
    request = Request("POST", "http://example.com/", b"secret=hunter2", {"X-Test": "exists"})
    before_record_request = _build_before_record_request(filter_headers=[("X-Test", "scrubbed")])

    filtered = before_record_request(request)

    assert filtered.body == b"secret=hunter2"
    assert filtered.headers["X-Test"] == "scrubbed"
    # the caller's request is untouched -- this is why the request is copied
    assert request.headers["X-Test"] == "exists"


def test_before_record_request_with_uncopyable_body():
    """A body holding an open file can't be deepcopied.

    The request must be filtered in place instead of raising
    ``TypeError: cannot pickle '_io.BufferedReader' object`` (#737).
    """
    before_record_request = _build_before_record_request(
        filter_post_data_parameters=[("secret", "REDACTED")],
    )

    with tempfile.TemporaryFile() as fileobj:
        fileobj.write(b"payload")
        fileobj.seek(0)
        request = Request("POST", "http://example.com/", {"secret": "hunter2", "file": fileobj}, {})
        filtered = before_record_request(request)

        # no copy could be made, so the original request was filtered in place
        assert filtered is request
        assert filtered.body["secret"] == "REDACTED"
        # the file itself is left alone
        assert filtered.body["file"] is fileobj
        assert filtered.body["file"].read() == b"payload"
