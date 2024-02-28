"""Tests for cassettes with custom persistence"""

# External imports
import os
from urllib.request import urlopen

import pytest

# Internal imports
import vcr
from vcr.persisters.filesystem import CassetteDecodeError, CassetteNotFoundError, FilesystemPersister


class CustomFilesystemPersister:
    """Behaves just like default FilesystemPersister but adds .test extension
    to the cassette file"""

    @staticmethod
    def load_cassette(cassette_path, serializer):
        cassette_path += ".test"
        return FilesystemPersister.load_cassette(cassette_path, serializer)

    @staticmethod
    def save_cassette(cassette_path, cassette_dict, serializer):
        cassette_path += ".test"
        FilesystemPersister.save_cassette(cassette_path, cassette_dict, serializer)


class BadPersister(FilesystemPersister):
    """A bad persister that raises different errors."""

    @staticmethod
    def load_cassette(cassette_path, serializer):
        if "nonexistent" in cassette_path:
            raise CassetteNotFoundError()
        elif "encoding" in cassette_path:
            raise CassetteDecodeError()
        else:
            raise ValueError("buggy persister")


def test_save_cassette_with_custom_persister(tmpdir, httpbin):
    """Ensure you can save a cassette using custom persister"""
    my_vcr = vcr.VCR()
    my_vcr.register_persister(CustomFilesystemPersister)

    # Check to make sure directory doesn't exist
    assert not os.path.exists(str(tmpdir.join("nonexistent")))

    # Run VCR to create dir and cassette file using new save_cassette callback
    with my_vcr.use_cassette(str(tmpdir.join("nonexistent", "cassette.yml"))):
        urlopen(httpbin.url).read()

    # Callback should have made the file and the directory
    assert os.path.exists(str(tmpdir.join("nonexistent", "cassette.yml.test")))


def test_load_cassette_with_custom_persister(tmpdir, httpbin):
    """
    Ensure you can load a cassette using custom persister
    """
    my_vcr = vcr.VCR()
    my_vcr.register_persister(CustomFilesystemPersister)

    test_fixture = str(tmpdir.join("synopsis.json.test"))

    with my_vcr.use_cassette(test_fixture, serializer="json"):
        response = urlopen(httpbin.url).read()
        assert b"HTTP Request &amp; Response Service" in response


def test_load_cassette_persister_exception_handling(tmpdir, httpbin):
    """
    Ensure expected errors from persister are swallowed while unexpected ones
    are passed up the call stack.
    """
    my_vcr = vcr.VCR()
    my_vcr.register_persister(BadPersister)

    with my_vcr.use_cassette("bad/nonexistent") as cass:
        assert len(cass) == 0

    with my_vcr.use_cassette("bad/encoding") as cass:
        assert len(cass) == 0

    with pytest.raises(ValueError):
        with my_vcr.use_cassette("bad/buggy") as cass:
            pass
