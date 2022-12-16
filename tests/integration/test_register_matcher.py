from urllib.request import urlopen

import pytest

import vcr


def true_matcher(r1, r2):
    return True


def false_matcher(r1, r2):
    return False


@pytest.mark.online
def test_registered_true_matcher(tmpdir, mockbin_request_url):
    my_vcr = vcr.VCR()
    my_vcr.register_matcher("true", true_matcher)
    testfile = str(tmpdir.join("test.yml"))
    with my_vcr.use_cassette(testfile, match_on=["true"]):
        # These 2 different urls are stored as the same request
        urlopen(mockbin_request_url)
        urlopen(mockbin_request_url + "/get")

    with my_vcr.use_cassette(testfile, match_on=["true"]):
        # I can get the response twice even though I only asked for it once
        urlopen(mockbin_request_url)
        urlopen(mockbin_request_url)


@pytest.mark.online
def test_registered_false_matcher(tmpdir, mockbin_request_url):
    my_vcr = vcr.VCR()
    my_vcr.register_matcher("false", false_matcher)
    testfile = str(tmpdir.join("test.yml"))
    with my_vcr.use_cassette(testfile, match_on=["false"]) as cass:
        # These 2 different urls are stored as different requests
        urlopen(mockbin_request_url)
        urlopen(mockbin_request_url + "/get")
        assert len(cass) == 2
