"""Basic tests about save behavior"""

# External imports
import os
import time
from urllib.request import urlopen

import pytest

# Internal imports
import vcr


@pytest.mark.online
def test_disk_saver_nowrite(tmpdir, mockbin_request_url):
    """
    Ensure that when you close a cassette without changing it it doesn't
    rewrite the file
    """
    fname = str(tmpdir.join("synopsis.yaml"))
    with vcr.use_cassette(fname) as cass:
        urlopen(mockbin_request_url).read()
        assert cass.play_count == 0
    last_mod = os.path.getmtime(fname)

    with vcr.use_cassette(fname) as cass:
        urlopen(mockbin_request_url).read()
        assert cass.play_count == 1
        assert cass.dirty is False
    last_mod2 = os.path.getmtime(fname)

    assert last_mod == last_mod2


@pytest.mark.online
def test_disk_saver_write(tmpdir, mockbin_request_url):
    """
    Ensure that when you close a cassette after changing it it does
    rewrite the file
    """
    fname = str(tmpdir.join("synopsis.yaml"))
    with vcr.use_cassette(fname) as cass:
        urlopen(mockbin_request_url).read()
        assert cass.play_count == 0
    last_mod = os.path.getmtime(fname)

    # Make sure at least 1 second passes, otherwise sometimes
    # the mtime doesn't change
    time.sleep(1)

    with vcr.use_cassette(fname, record_mode=vcr.mode.ANY) as cass:
        urlopen(mockbin_request_url).read()
        urlopen(mockbin_request_url + "/get").read()
        assert cass.play_count == 1
        assert cass.dirty
    last_mod2 = os.path.getmtime(fname)

    assert last_mod != last_mod2
