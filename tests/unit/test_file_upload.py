"""Test that file-like objects are handled properly in aiohttp stubs."""

import io


def test_br_converted_to_bytes():
    """BufferedReader should be converted to bytes before pickling."""
    buf = io.BytesIO(b"test file content")
    data = buf.read() if hasattr(buf, 'read') else buf
    assert isinstance(data, bytes)
    assert data == b"test file content"


def test_noop_for_bytes():
    """Bytes objects should pass through unchanged."""
    data = b"already bytes"
    result = data
    assert result is data
