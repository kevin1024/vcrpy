from io import BytesIO, StringIO

import pytest

from vcr import request
from vcr.util import read_body


@pytest.mark.parametrize(
    "input_, expected_output",
    [
        (BytesIO(b"Stream"), b"Stream"),
        (StringIO("Stream"), b"Stream"),
        (iter(["StringIter"]), b"StringIter"),
        (iter(["String", "Iter"]), b"StringIter"),
        (iter([b"BytesIter"]), b"BytesIter"),
        (iter([b"Bytes", b"Iter"]), b"BytesIter"),
        (iter([70, 111, 111]), b"Foo"),
        (iter([]), b""),
        ("String", b"String"),
        (b"Bytes", b"Bytes"),
    ],
)
def test_read_body(input_, expected_output):
    r = request.Request("POST", "http://host.com/", input_, {})
    assert read_body(r) == expected_output


def test_unsupported_read_body():
    r = request.Request("POST", "http://host.com/", iter([[]]), {})
    with pytest.raises(ValueError) as excinfo:
        assert read_body(r)
    assert excinfo.value.args == ("Body type <class 'list'> not supported",)
