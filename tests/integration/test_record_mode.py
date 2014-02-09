import os
import pytest
import vcr
from vcr._compat import urlopen


def test_once_record_mode(tmpdir):
    testfile = str(tmpdir.join('recordmode.yml'))
    with vcr.use_cassette(testfile, record_mode="once"):
        # cassette file doesn't exist, so create.
        response = urlopen('http://httpbin.org/').read()

    with vcr.use_cassette(testfile, record_mode="once") as cass:
        # make the same request again
        response = urlopen('http://httpbin.org/').read()

        # the first time, it's played from the cassette.
        # but, try to access something else from the same cassette, and an
        # exception is raised.
        with pytest.raises(Exception):
            response = urlopen('http://httpbin.org/get').read()


def test_once_record_mode_two_times(tmpdir):
    testfile = str(tmpdir.join('recordmode.yml'))
    with vcr.use_cassette(testfile, record_mode="once"):
        # get two of the same file
        response1 = urlopen('http://httpbin.org/').read()
        response2 = urlopen('http://httpbin.org/').read()

    with vcr.use_cassette(testfile, record_mode="once") as cass:
        # do it again
        response = urlopen('http://httpbin.org/').read()
        response = urlopen('http://httpbin.org/').read()


def test_once_mode_three_times(tmpdir):
    testfile = str(tmpdir.join('recordmode.yml'))
    with vcr.use_cassette(testfile, record_mode="once"):
        # get three of the same file
        response1 = urlopen('http://httpbin.org/').read()
        response2 = urlopen('http://httpbin.org/').read()
        response2 = urlopen('http://httpbin.org/').read()


def test_new_episodes_record_mode(tmpdir):
    testfile = str(tmpdir.join('recordmode.yml'))

    with vcr.use_cassette(testfile, record_mode="new_episodes"):
        # cassette file doesn't exist, so create.
        response = urlopen('http://httpbin.org/').read()

    with vcr.use_cassette(testfile, record_mode="new_episodes") as cass:
        # make the same request again
        response = urlopen('http://httpbin.org/').read()

        # in the "new_episodes" record mode, we can add more requests to
        # a cassette without repurcussions.
        response = urlopen('http://httpbin.org/get').read()

        # the first interaction was not re-recorded, but the second was added
        assert cass.play_count == 1


def test_all_record_mode(tmpdir):
    testfile = str(tmpdir.join('recordmode.yml'))

    with vcr.use_cassette(testfile, record_mode="all"):
        # cassette file doesn't exist, so create.
        response = urlopen('http://httpbin.org/').read()

    with vcr.use_cassette(testfile, record_mode="all") as cass:
        # make the same request again
        response = urlopen('http://httpbin.org/').read()

        # in the "all" record mode, we can add more requests to
        # a cassette without repurcussions.
        response = urlopen('http://httpbin.org/get').read()

        # The cassette was never actually played, even though it existed.
        # that's because, in "all" mode, the requests all go directly to
        # the source and bypass the cassette.
        assert cass.play_count == 0


def test_none_record_mode(tmpdir):
    # Cassette file doesn't exist, yet we are trying to make a request.
    # raise hell.
    testfile = str(tmpdir.join('recordmode.yml'))
    with vcr.use_cassette(testfile, record_mode="none"):
        with pytest.raises(Exception):
            response = urlopen('http://httpbin.org/').read()


def test_none_record_mode_with_existing_cassette(tmpdir):
    # create a cassette file
    testfile = str(tmpdir.join('recordmode.yml'))

    with vcr.use_cassette(testfile, record_mode="all"):
        response = urlopen('http://httpbin.org/').read()

    # play from cassette file
    with vcr.use_cassette(testfile, record_mode="none") as cass:
        response = urlopen('http://httpbin.org/').read()
        assert cass.play_count == 1
        # but if I try to hit the net, raise an exception.
        with pytest.raises(Exception):
            response = urlopen('http://httpbin.org/get').read()
