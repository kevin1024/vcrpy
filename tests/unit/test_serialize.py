from unittest import mock

import pytest

from vcr.request import Request
from vcr.serialize import deserialize, serialize
from vcr.serializers import compat, jsonserializer, yamlserializer


def test_deserialize_old_yaml_cassette():
    with open("tests/fixtures/migration/old_cassette.yaml") as f, pytest.raises(ValueError):
        deserialize(f.read(), yamlserializer)


def test_deserialize_yaml_cassette_does_not_execute_python_object_tags(tmpdir):
    # A malicious cassette must not be able to execute arbitrary code via
    # PyYAML's ``!!python/object/apply`` tag when it is loaded.
    marker = tmpdir.join("pwned")
    malicious = (
        "interactions:\n"
        "- request:\n"
        "    body: null\n"
        "    headers: {}\n"
        "    method: GET\n"
        "    uri: http://example.com/\n"
        "  response:\n"
        "    body: {string: ok}\n"
        "    headers: {}\n"
        "    status: {code: 200, message: OK}\n"
        f"_x: !!python/object/apply:os.system ['touch {marker}']\n"
        "version: 1\n"
    )
    # The dangerous tag is rejected with a ValueError rather than executed.
    with pytest.raises(ValueError):
        deserialize(malicious, yamlserializer)
    assert not marker.check(), "malicious cassette executed code during load"


def test_deserialize_yaml_cassette_unknown_tag_gives_clear_error():
    # A cassette with an unrecognized Python object tag (e.g. a custom class)
    # used to raise "Your cassette files were generated in an older version of
    # VCR", even for freshly re-recorded cassettes. It should now raise a
    # clear, descriptive ValueError instead.
    cassette_with_custom_tag = (
        "interactions:\n"
        "- request:\n"
        "    body: !!python/object/new:some.custom.Object\n"
        "      state: [hello]\n"
        "    headers: {}\n"
        "    method: GET\n"
        "    uri: http://example.com/\n"
        "  response:\n"
        "    body: {string: ok}\n"
        "    headers: {}\n"
        "    status: {code: 200, message: OK}\n"
        "version: 1\n"
    )
    with pytest.raises(ValueError, match="There was a problem loading the cassette") as excinfo:
        deserialize(cassette_with_custom_tag, yamlserializer)
    # The old misleading message must not appear
    assert "older version of VCR" not in excinfo.exconly()


def test_deserialize_yaml_cassette_allows_safe_python_tuple_and_str():
    # Legitimate cassettes (e.g. from the tornado stub) contain benign
    # ``!!python/tuple``/``!!python/unicode`` tags that must still load.
    yaml_str = (
        "interactions:\n"
        "- request:\n"
        "    body: null\n"
        "    headers: !!python/tuple\n"
        "    - !!python/unicode 'Accept'\n"
        "    - ['*/*']\n"
        "    method: GET\n"
        "    uri: http://example.com/\n"
        "  response:\n"
        "    body: {string: ok}\n"
        "    headers: {}\n"
        "    status: {code: 200, message: OK}\n"
        "version: 1\n"
    )
    data = yamlserializer.deserialize(yaml_str)
    assert isinstance(data["interactions"][0]["request"]["headers"], tuple)


def test_deserialize_old_json_cassette():
    with open("tests/fixtures/migration/old_cassette.json") as f, pytest.raises(ValueError):
        deserialize(f.read(), jsonserializer)


def test_deserialize_new_yaml_cassette():
    with open("tests/fixtures/migration/new_cassette.yaml") as f:
        deserialize(f.read(), yamlserializer)


def test_deserialize_new_json_cassette():
    with open("tests/fixtures/migration/new_cassette.json") as f:
        deserialize(f.read(), jsonserializer)


REQBODY_TEMPLATE = """\
interactions:
- request:
    body: {req_body}
    headers:
      Content-Type: [application/x-www-form-urlencoded]
      Host: [httpbin.org]
    method: POST
    uri: http://httpbin.org/post
  response:
    body: {{string: ""}}
    headers:
      content-length: ['0']
      content-type: [application/json]
    status: {{code: 200, message: OK}}
"""


# A cassette generated under Python 2 stores the request body as a string,
# but the same cassette generated under Python 3 stores it as "!!binary".
# Make sure we accept both forms, regardless of whether we're running under
# Python 2 or 3.
@pytest.mark.parametrize(
    "req_body, expect",
    [
        # Cassette written under Python 2 (pure ASCII body)
        ("x=5&y=2", b"x=5&y=2"),
        # Cassette written under Python 3 (pure ASCII body)
        ("!!binary |\n      eD01Jnk9Mg==", b"x=5&y=2"),
        # Request body has non-ASCII chars (x=föo&y=2), encoded in UTF-8.
        ('!!python/str "x=f\\xF6o&y=2"', b"x=f\xc3\xb6o&y=2"),
        ("!!binary |\n      eD1mw7ZvJnk9Mg==", b"x=f\xc3\xb6o&y=2"),
        # Same request body, this time encoded in UTF-16. In this case, we
        # write the same YAML file under both Python 2 and 3, so there's only
        # one test case here.
        (
            "!!binary |\n      //54AD0AZgD2AG8AJgB5AD0AMgA=",
            b"\xff\xfex\x00=\x00f\x00\xf6\x00o\x00&\x00y\x00=\x002\x00",
        ),
        # Same again, this time encoded in ISO-8859-1.
        ("!!binary |\n      eD1m9m8meT0y", b"x=f\xf6o&y=2"),
    ],
)
def test_deserialize_py2py3_yaml_cassette(tmpdir, req_body, expect):
    cfile = tmpdir.join("test_cassette.yaml")
    cfile.write(REQBODY_TEMPLATE.format(req_body=req_body))
    with open(str(cfile)) as f:
        (requests, _) = deserialize(f.read(), yamlserializer)
    assert requests[0].body == expect


@mock.patch.object(
    jsonserializer.json,
    "dumps",
    side_effect=UnicodeDecodeError("utf-8", b"unicode error in serialization", 0, 10, "blew up"),
)
def test_serialize_constructs_UnicodeDecodeError(mock_dumps):
    with pytest.raises(UnicodeDecodeError):
        jsonserializer.serialize({})


def test_serialize_empty_request():
    request = Request(method="POST", uri="http://localhost/", body="", headers={})

    serialize({"requests": [request], "responses": [{}]}, jsonserializer)


def test_serialize_json_request():
    request = Request(method="POST", uri="http://localhost/", body="{'hello': 'world'}", headers={})

    serialize({"requests": [request], "responses": [{}]}, jsonserializer)


def test_serialize_binary_request():
    msg = "Does this HTTP interaction contain binary data?"

    request = Request(method="POST", uri="http://localhost/", body=b"\x8c", headers={})

    try:
        serialize({"requests": [request], "responses": [{}]}, jsonserializer)
    except (UnicodeDecodeError, TypeError) as exc:
        assert msg in str(exc)


def test_deserialize_no_body_string():
    data = {"body": {"string": None}}
    output = compat.convert_to_bytes(data)
    assert data == output
