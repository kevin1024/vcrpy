import os
from unittest import mock
from urllib.request import urlopen

import pytest

import vcr
from vcr import errors
from vcr.cassette import Cassette


@mock.patch("vcr.cassette.Cassette.find_requests_with_most_matches")
@pytest.mark.parametrize(
    "most_matches, expected_message",
    [
        # No request match found
        ([], "No similar requests, that have not been played, found."),
        # One matcher failed
        (
            [("similar request", ["method", "path"], [("query", "failed : query")])],
            "Found 1 similar requests with 1 different matcher(s) :\n"
            "\n1 - ('similar request').\n"
            "Matchers succeeded : ['method', 'path']\n"
            "Matchers failed :\n"
            "query - assertion failure :\n"
            "failed : query\n",
        ),
        # Multiple failed matchers
        (
            [("similar request", ["method"], [("query", "failed : query"), ("path", "failed : path")])],
            "Found 1 similar requests with 2 different matcher(s) :\n"
            "\n1 - ('similar request').\n"
            "Matchers succeeded : ['method']\n"
            "Matchers failed :\n"
            "query - assertion failure :\n"
            "failed : query\n"
            "path - assertion failure :\n"
            "failed : path\n",
        ),
        # Multiple similar requests
        (
            [
                ("similar request", ["method"], [("query", "failed : query")]),
                ("similar request 2", ["method"], [("query", "failed : query 2")]),
            ],
            "Found 2 similar requests with 1 different matcher(s) :\n"
            "\n1 - ('similar request').\n"
            "Matchers succeeded : ['method']\n"
            "Matchers failed :\n"
            "query - assertion failure :\n"
            "failed : query\n"
            "\n2 - ('similar request 2').\n"
            "Matchers succeeded : ['method']\n"
            "Matchers failed :\n"
            "query - assertion failure :\n"
            "failed : query 2\n",
        ),
        # One matcher succeeded, must be already played
        (
            [("similar request", ["method", "path", "query"], [])],
            "Found 1 recorded request(s) matching ('request') but they have already been consumed.\n",
        ),
    ],
)
def test_CannotOverwriteExistingCassetteException_get_message(
    mock_find_requests_with_most_matches,
    most_matches,
    expected_message,
):
    mock_find_requests_with_most_matches.return_value = most_matches
    cassette = Cassette("path")
    failed_request = "request"
    exception_message = errors.CannotOverwriteExistingCassetteException._get_message(cassette, "request")
    expected = (
        f"Can't overwrite existing cassette ({cassette._path!r}) "
        f"in your current record mode ({cassette.record_mode!r}).\n"
        f"No match for the request ({failed_request!r}) was found.\n"
        f"{expected_message}"
    )
    assert exception_message == expected


def test_none_record_mode_missing_cassette_message(tmpdir):
    """Regression test for #838.

    When the cassette does not exist and the record mode forbids recording
    (e.g. ``none``), the raised ``CannotOverwriteExistingCassetteException``
    must not claim we are "overwriting an existing cassette" — there is no
    cassette to overwrite. The message should explain that the cassette is
    missing and the current record mode does not allow recording a new one.
    """
    path = str(tmpdir.join("does_not_exist.yml"))
    assert not os.path.exists(path)

    with (
        pytest.raises(vcr.errors.CannotOverwriteExistingCassetteException) as excinfo,
        vcr.use_cassette(path, record_mode=vcr.mode.NONE),
    ):
        # The exception is raised before any network access happens, so a
        # non-routable URL is sufficient and keeps the test offline.
        urlopen("http://vcr-regression-test.invalid/")

    message = str(excinfo.value)
    assert "does not exist" in message
    assert "overwrite existing cassette" not in message
