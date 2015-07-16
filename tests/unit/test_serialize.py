import pytest

from vcr.compat import mock
from vcr.serialize import deserialize
from vcr.serializers import yamlserializer, jsonserializer


def test_deserialize_old_yaml_cassette():
    with open('tests/fixtures/migration/old_cassette.yaml', 'r') as f:
        with pytest.raises(ValueError):
            deserialize(f.read(), yamlserializer)


def test_deserialize_old_json_cassette():
    with open('tests/fixtures/migration/old_cassette.json', 'r') as f:
        with pytest.raises(ValueError):
            deserialize(f.read(), jsonserializer)


def test_deserialize_new_yaml_cassette():
    with open('tests/fixtures/migration/new_cassette.yaml', 'r') as f:
        deserialize(f.read(), yamlserializer)


def test_deserialize_new_json_cassette():
    with open('tests/fixtures/migration/new_cassette.json', 'r') as f:
        deserialize(f.read(), jsonserializer)


REQBODY_TEMPLATE = u'''\
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
'''


# A cassette generated under Python 2 stores the request body as a string,
# but the same cassette generated under Python 3 stores it as "!!binary".
# Make sure we accept both forms, regardless of whether we're running under
# Python 2 or 3.
@pytest.mark.parametrize("req_body, expect", [
    # Cassette written under Python 2 (pure ASCII body)
    ('x=5&y=2', b'x=5&y=2'),
    # Cassette written under Python 3 (pure ASCII body)
    ('!!binary |\n      eD01Jnk9Mg==', b'x=5&y=2'),
])
def test_deserialize_py2py3_yaml_cassette(tmpdir, req_body, expect):
    cfile = tmpdir.join('test_cassette.yaml')
    cfile.write(REQBODY_TEMPLATE.format(req_body=req_body))
    with open(str(cfile)) as f:
        (requests, responses) = deserialize(f.read(), yamlserializer)
    assert requests[0].body == expect


@mock.patch.object(jsonserializer.json, 'dumps',
                   side_effect=UnicodeDecodeError('utf-8', b'unicode error in serialization',
                                                  0, 10, 'blew up'))
def test_serialize_constructs_UnicodeDecodeError(mock_dumps):
    with pytest.raises(UnicodeDecodeError):
        jsonserializer.serialize({})
