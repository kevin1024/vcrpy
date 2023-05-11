import json
import os
from urllib.request import urlopen

import pytest

import vcr


def test_set_serializer_default_config(tmpdir, mockbin_request_url):
    my_vcr = vcr.VCR(serializer="json")

    with my_vcr.use_cassette(str(tmpdir.join("test.json"))):
        assert my_vcr.serializer == "json"
        urlopen(mockbin_request_url)

    with open(str(tmpdir.join("test.json"))) as f:
        file_content = f.read()
        assert file_content.endswith("\n")
        assert json.loads(file_content)


def test_default_set_cassette_library_dir(tmpdir, mockbin_request_url):
    my_vcr = vcr.VCR(cassette_library_dir=str(tmpdir.join("subdir")))

    with my_vcr.use_cassette("test.json"):
        urlopen(mockbin_request_url)

    assert os.path.exists(str(tmpdir.join("subdir").join("test.json")))


def test_override_set_cassette_library_dir(tmpdir, mockbin_request_url):
    my_vcr = vcr.VCR(cassette_library_dir=str(tmpdir.join("subdir")))

    cld = str(tmpdir.join("subdir2"))

    with my_vcr.use_cassette("test.json", cassette_library_dir=cld):
        urlopen(mockbin_request_url)

    assert os.path.exists(str(tmpdir.join("subdir2").join("test.json")))
    assert not os.path.exists(str(tmpdir.join("subdir").join("test.json")))


def test_override_match_on(tmpdir, mockbin_request_url):
    my_vcr = vcr.VCR(match_on=["method"])

    with my_vcr.use_cassette(str(tmpdir.join("test.json"))):
        urlopen(mockbin_request_url)

    with my_vcr.use_cassette(str(tmpdir.join("test.json"))) as cass:
        urlopen(mockbin_request_url)

    assert len(cass) == 1
    assert cass.play_count == 1


def test_missing_matcher():
    my_vcr = vcr.VCR()
    my_vcr.register_matcher("awesome", object)
    with pytest.raises(KeyError):
        with my_vcr.use_cassette("test.yaml", match_on=["notawesome"]):
            pass


def test_dont_record_on_exception(tmpdir, mockbin_request_url):
    my_vcr = vcr.VCR(record_on_exception=False)

    @my_vcr.use_cassette(str(tmpdir.join("dontsave.yml")))
    def some_test():
        assert b"Not in content" in urlopen(mockbin_request_url)

    with pytest.raises(AssertionError):
        some_test()

    assert not os.path.exists(str(tmpdir.join("dontsave.yml")))

    # Make sure context decorator has the same behavior
    with pytest.raises(AssertionError):
        with my_vcr.use_cassette(str(tmpdir.join("dontsave2.yml"))):
            assert b"Not in content" in urlopen(mockbin_request_url).read()

    assert not os.path.exists(str(tmpdir.join("dontsave2.yml")))
