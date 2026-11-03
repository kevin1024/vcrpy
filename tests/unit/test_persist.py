import json
import subprocess
import sys
from pathlib import Path

import pytest

from vcr.persisters.filesystem import CassetteNotFoundError, FilesystemPersister
from vcr.request import Request
from vcr.serializers import jsonserializer, yamlserializer

# A cassette file holding raw (unescaped) UTF-8 text, like cassettes that have
# been edited by hand, or written by a serializer that doesn't escape non-ASCII.
CASSETTE_WITH_UTF8 = """\
interactions:
- request:
    body: null
    headers: {}
    method: GET
    uri: http://example.com/café
  response:
    body:
      string: café ☃
    headers: {}
    status:
      code: 200
      message: OK
version: 1
"""


class _Utf8JsonSerializer:
    """A JSON serializer that leaves non-ASCII text as text, as custom serializers can."""

    @staticmethod
    def deserialize(cassette_string):
        return json.loads(cassette_string)

    @staticmethod
    def serialize(cassette_dict):
        return json.dumps(cassette_dict, ensure_ascii=False) + "\n"


@pytest.mark.parametrize(
    "cassette_path, serializer, expected_message",
    [
        # Old JSON cassettes are recognized as old-format and pointed at the
        # migration script.
        ("tests/fixtures/migration/old_cassette.json", jsonserializer, "run the migration script"),
        # Old YAML cassettes contain python object tags the safe loader
        # refuses, so they surface the unsupported-tag error instead.
        ("tests/fixtures/migration/old_cassette.yaml", yamlserializer, "problem loading the cassette"),
    ],
)
def test_load_cassette_with_old_cassettes(cassette_path, serializer, expected_message):
    with pytest.raises(ValueError) as excinfo:
        FilesystemPersister.load_cassette(cassette_path, serializer)
    assert expected_message in excinfo.exconly()


@pytest.mark.parametrize(
    "cassette_path, serializer",
    [
        ("tests/fixtures/migration/not_cassette.txt", jsonserializer),
        ("tests/fixtures/migration/not_cassette.txt", yamlserializer),
    ],
)
def test_load_cassette_with_invalid_cassettes(cassette_path, serializer):
    with pytest.raises(Exception) as excinfo:
        FilesystemPersister.load_cassette(cassette_path, serializer)
    assert "run the migration script" not in excinfo.exconly()


@pytest.mark.parametrize("content", ["", "\n"])
@pytest.mark.parametrize("serializer", [jsonserializer, yamlserializer])
def test_load_empty_cassette(tmpdir, serializer, content):
    cassette_path = tmpdir.join("empty_cassette")
    cassette_path.write(content)
    with pytest.raises(CassetteNotFoundError):
        FilesystemPersister.load_cassette(str(cassette_path), serializer)


def test_read_cassette_with_utf8_text(tmpdir):
    """Cassette files hold UTF-8 text, whatever the locale's encoding is.

    Reading them with the locale's encoding (cp936 or cp1252 on Windows, ASCII
    under ``LC_ALL=C``) raises ``UnicodeDecodeError`` or mangles the text, so a
    cassette holding non-ASCII text that wasn't escaped doesn't load, is treated
    as an empty one, and is then recorded over.
    """
    cassette_path = Path(str(tmpdir.join("utf8.yaml")))
    cassette_path.write_text(CASSETTE_WITH_UTF8, encoding="utf-8")

    requests, responses = FilesystemPersister.load_cassette(str(cassette_path), yamlserializer)

    assert requests[0].uri == "http://example.com/café"
    assert responses[0]["body"]["string"] == "café ☃".encode()


def test_write_cassette_with_utf8_text(tmpdir):
    """Cassettes are written as UTF-8 too, so text a serializer doesn't escape
    can be saved on systems whose locale encoding can't represent it."""
    cassette_path = Path(str(tmpdir.join("utf8.json")))
    request = Request("GET", "http://example.com/café", None, {})
    response = {
        "status": {"code": 200, "message": "OK"},
        "headers": {},
        "body": {"string": "café ☃".encode()},
    }

    FilesystemPersister.save_cassette(
        str(cassette_path),
        {"requests": [request], "responses": [response]},
        _Utf8JsonSerializer,
    )

    assert "café ☃".encode() in cassette_path.read_bytes()


def test_filesystem_persister_specifies_an_encoding(tmpdir):
    """The persister is explicit about the encoding rather than using the
    locale's, which Python reports as an ``EncodingWarning`` when it is asked to
    warn about the implicit locale encoding (``-X warn_default_encoding``)."""
    cassette_path = str(tmpdir.join("cassette.yaml"))
    script = (
        "from vcr.persisters.filesystem import FilesystemPersister\n"
        "from vcr.serializers import yamlserializer\n"
        f"path = {cassette_path!r}\n"
        "cassette = {'requests': [], 'responses': []}\n"
        "FilesystemPersister.save_cassette(path, cassette, yamlserializer)\n"
        "FilesystemPersister.load_cassette(path, yamlserializer)\n"
    )

    subprocess.run(
        [sys.executable, "-X", "warn_default_encoding", "-W", "error::EncodingWarning", "-c", script],
        check=True,
    )
