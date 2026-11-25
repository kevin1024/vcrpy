import gzip
import io
import zlib

from vcr.stubs import VCRHTTPResponse


def _gzip_response(body, headers=None):
    recorded = {
        "status": {"message": "OK", "code": 200},
        "headers": {"Content-Encoding": ["gzip"]},
        "body": {"string": gzip.compress(body)},
    }
    if headers:
        recorded["headers"].update(headers)
    return recorded


def test_replayed_response_decodes_content_by_default():
    response = VCRHTTPResponse(_gzip_response(b'{"answer": 42}'))
    assert response.read() == b'{"answer": 42}'
    assert response.data == b'{"answer": 42}'


def test_replayed_response_returns_raw_bytes_with_decode_content_false():
    response = VCRHTTPResponse(_gzip_response(b'{"answer": 42}'))
    raw = response.read(decode_content=False)
    assert gzip.decompress(raw) == b'{"answer": 42}'


def test_replayed_response_partial_reads_decode():
    response = VCRHTTPResponse(_gzip_response(b'{"answer": 42}'))
    assert response.read(5) + response.read() == b'{"answer": 42}'

    response = VCRHTTPResponse(_gzip_response(b'{"answer": 42}'))
    raw = response.read(5, decode_content=False) + response.read(decode_content=False)
    assert gzip.decompress(raw) == b'{"answer": 42}'


def test_replayed_response_decodes_deflate():
    response = VCRHTTPResponse(
        {
            "status": {"message": "OK", "code": 200},
            "headers": {"Content-Encoding": ["deflate"]},
            "body": {"string": zlib.compress(b'{"answer": 42}')},
        },
    )
    assert response.read() == b'{"answer": 42}'


def test_replayed_response_already_decoded_body_is_returned_as_is():
    # Cassettes recorded before raw storage kept an already-decoded body
    # next to its Content-Encoding header (#1116).
    response = VCRHTTPResponse(
        {
            "status": {"message": "OK", "code": 200},
            "headers": {"Content-Encoding": ["gzip"]},
            "body": {"string": b'{"answer": 42}'},
        },
    )
    assert response.read() == b'{"answer": 42}'
    assert response.read(decode_content=False) == b'{"answer": 42}'


def test_replayed_response_can_release_connection():
    response = VCRHTTPResponse(
        {
            "status": {"message": "OK", "code": 200},
            "headers": {},
            "body": {"string": b"recorded body"},
        },
    )

    assert response.read() == b"recorded body"
    assert response.release_conn() is None


def test_response_should_have_headers_field():
    recorded_response = {
        "status": {"message": "OK", "code": 200},
        "headers": {
            "content-length": ["0"],
            "server": ["gunicorn/18.0"],
            "connection": ["Close"],
            "access-control-allow-credentials": ["true"],
            "date": ["Fri, 24 Oct 2014 18:35:37 GMT"],
            "access-control-allow-origin": ["*"],
            "content-type": ["text/html; charset=utf-8"],
        },
        "body": {"string": b""},
    }
    response = VCRHTTPResponse(recorded_response)

    assert response.headers is not None


def test_response_headers_should_be_equal_to_msg():
    recorded_response = {
        "status": {"message": b"OK", "code": 200},
        "headers": {
            "content-length": ["0"],
            "server": ["gunicorn/18.0"],
            "connection": ["Close"],
            "content-type": ["text/html; charset=utf-8"],
        },
        "body": {"string": b""},
    }
    response = VCRHTTPResponse(recorded_response)

    assert response.headers == response.msg


def test_response_headers_should_have_correct_values():
    recorded_response = {
        "status": {"message": "OK", "code": 200},
        "headers": {
            "content-length": ["10806"],
            "date": ["Fri, 24 Oct 2014 18:35:37 GMT"],
            "content-type": ["text/html; charset=utf-8"],
        },
        "body": {"string": b""},
    }
    response = VCRHTTPResponse(recorded_response)

    assert response.headers.get("content-length") == "10806"
    assert response.headers.get("date") == "Fri, 24 Oct 2014 18:35:37 GMT"


def test_response_parses_correctly_and_fp_attribute_error_is_not_thrown():
    """
    Regression test for https://github.com/kevin1024/vcrpy/issues/440
    :return:
    """
    recorded_response = {
        "status": {"message": "OK", "code": 200},
        "headers": {
            "content-length": ["0"],
            "server": ["gunicorn/18.0"],
            "connection": ["Close"],
            "access-control-allow-credentials": ["true"],
            "date": ["Fri, 24 Oct 2014 18:35:37 GMT"],
            "access-control-allow-origin": ["*"],
            "content-type": ["text/html; charset=utf-8"],
        },
        "body": {
            "string": b"\nPMID- 19416910\nOWN - NLM\nSTAT- MEDLINE\nDA  - 20090513\nDCOM- "
            b"20090622\nLR  - "
            b"20141209\nIS  - 1091-6490 (Electronic)\nIS  - 0027-8424 (Linking)\nVI  - "
            b"106\nIP  - "
            b"19\nDP  - 2009 May 12\nTI  - Genetic dissection of histone deacetylase "
            b"requirement in "
            b"tumor cells.\nPG  - 7751-5\nLID - 10.1073/pnas.0903139106 [doi]\nAB  - "
            b"Histone "
            b"deacetylase inhibitors (HDACi) represent a new group of drugs currently\n "
            b"     being "
            b"tested in a wide variety of clinical applications. They are especially\n  "
            b"    effective "
            b"in preclinical models of cancer where they show antiproliferative\n      "
            b"action in many "
            b"different types of cancer cells. Recently, the first HDACi was\n      "
            b"approved for the "
            b"treatment of cutaneous T cell lymphomas. Most HDACi currently in\n      "
            b"clinical ",
        },
    }
    vcr_response = VCRHTTPResponse(recorded_response)
    handle = io.TextIOWrapper(vcr_response, encoding="utf-8")
    handle = iter(handle)
    articles = list(handle)
    assert len(articles) > 1


def test_replayed_response_decodes_json():
    response = VCRHTTPResponse(
        {
            "status": {"message": "OK", "code": 200},
            "headers": {"Content-Type": ["application/json"]},
            "body": {"string": b'{"answer": 42}'},
        },
    )

    assert response.json() == {"answer": 42}
