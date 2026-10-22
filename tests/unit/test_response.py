import io

from vcr.stubs import VCRHTTPResponse


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


def test_response_headers_should_match_msg():
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

    # ``headers`` is a multidict (like the ``HTTPHeaderDict`` on a real
    # urllib3 response), not the ``HTTPMessage`` itself, but it must
    # carry exactly the headers the message carries.
    for key, values in recorded_response["headers"].items():
        assert response.headers.getlist(key) == values
        assert response.msg.get_all(key) == values


def test_response_headers_preserve_duplicate_values():
    # Regression test for https://github.com/kevin1024/vcrpy/issues/947
    # Repeated headers were stored correctly in the cassette, but only
    # the first value survived on the stub response's ``headers`` when
    # read back through mapping-style access (e.g. by requests).
    recorded_response = {
        "status": {"message": "OK", "code": 200},
        "headers": {
            "content-length": ["2"],
            "link": ['<foo>; rel="foo"', '<bar>; rel="bar"'],
            "set-cookie": ["a=1; Path=/", "b=2; Path=/"],
        },
        "body": {"string": b"{}"},
    }
    response = VCRHTTPResponse(recorded_response)

    assert response.headers.getlist("link") == ['<foo>; rel="foo"', '<bar>; rel="bar"']
    assert response.headers.getlist("set-cookie") == ["a=1; Path=/", "b=2; Path=/"]
    assert response.headers["link"] == '<foo>; rel="foo", <bar>; rel="bar"'
    assert sorted(v for k, v in response.headers.items() if k.lower() == "link") == [
        '<bar>; rel="bar"',
        '<foo>; rel="foo"',
    ]
    assert response.getheader("link") == '<foo>; rel="foo", <bar>; rel="bar"'
    assert response.msg.get_all("link") == ['<foo>; rel="foo"', '<bar>; rel="bar"']


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
