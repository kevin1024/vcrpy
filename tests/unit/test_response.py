# coding: UTF-8
from vcr.stubs import VCRHTTPResponse


def test_response_should_have_headers_field():
    recorded_response = {
        "status": {
            "message": "OK",
            "code": 200
        },
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
            "string": b""
        }
    }
    response = VCRHTTPResponse(recorded_response)

    assert response.headers is not None


def test_response_headers_should_be_equal_to_msg():
    recorded_response = {
        "status": {
            "message": b"OK",
            "code": 200
        },
        "headers": {
            "content-length": ["0"],
            "server": ["gunicorn/18.0"],
            "connection": ["Close"],
            "content-type": ["text/html; charset=utf-8"],
        },
        "body": {
            "string": b""
        }
    }
    response = VCRHTTPResponse(recorded_response)

    assert response.headers == response.msg


def test_response_headers_should_have_correct_values():
    recorded_response = {
        "status": {
            "message": "OK",
            "code": 200
        },
        "headers": {
            "content-length": ["10806"],
            "date": ["Fri, 24 Oct 2014 18:35:37 GMT"],
            "content-type": ["text/html; charset=utf-8"],
        },
        "body": {
            "string": b""
        }
    }
    response = VCRHTTPResponse(recorded_response)

    assert response.headers.get('content-length') == "10806"
    assert response.headers.get('date') == "Fri, 24 Oct 2014 18:35:37 GMT"
