from unittest import mock

import pytest

from vcr import errors
from vcr.cassette import Cassette
from vcr.record_mode import RecordMode
from vcr.request import Request


def _request(uri="http://example.com/foo", method="GET", body=None):
    return Request(method, uri, body, {})


def _cassette(record_mode=RecordMode.ONCE, loaded=True, recorded=1, **kwargs):
    cassette = Cassette("path/to/cassette.yaml", record_mode=record_mode, **kwargs)
    for i in range(recorded):
        cassette.data.append((_request(f"http://example.com/recorded/{i}"), {}))
    cassette.rewound = loaded
    return cassette


def _exception(cassette, similar_requests, request=None):
    with mock.patch.object(Cassette, "find_requests_with_most_matches", return_value=similar_requests):
        return errors.CannotOverwriteExistingCassetteException(
            cassette=cassette,
            failed_request=request or _request(),
        )


def test_attributes():
    cassette = _cassette()
    request = _request()
    similar = [(_request("http://example.com/bar"), ["method"], [("path", "/foo != /bar")])]
    exc = _exception(cassette, similar, request)
    assert exc.cassette is cassette
    assert exc.failed_request is request
    assert exc.similar_requests == similar
    assert exc.reason == "no_match"


def test_cassette_not_found():
    exc = _exception(_cassette(record_mode=RecordMode.NONE, loaded=False, recorded=0), [])
    message = str(exc)
    assert exc.reason == "cassette_not_found"
    assert message.splitlines()[0] == (
        "Can't play back this request: the cassette doesn't exist, "
        "and record_mode 'none' doesn't record new ones."
    )
    assert "record_mode='once'" in message
    assert "cassette_library_dir" in message


def test_already_played():
    similar = [(_request(), ["method", "scheme", "host", "port", "path", "query"], [])]
    exc = _exception(_cassette(record_mode=RecordMode.NONE), similar)
    message = str(exc)
    assert exc.reason == "already_played"
    assert message.splitlines()[:2] == [
        (
            "Can't play back this request: it matches 1 recorded interaction, "
            "but that has already been played back."
        ),
        "record_mode 'none' doesn't record new requests.",
    ]
    assert "allow_playback_repeats=True" in message
    assert "advanced.html#playback-repeats" in message


def test_already_played_several():
    similar = [(_request(), ["method"], []), (_request(), ["method"], [])]
    message = str(_exception(_cassette(recorded=2), similar))
    assert "it matches 2 recorded interactions, but they have all been played back" in message


def test_no_match_shows_closest_requests():
    similar = [(_request("http://example.com/foo"), ["method", "path"], [("query", "[('page', '2')] != []")])]
    exc = _exception(_cassette(), similar, _request("http://example.com/foo?page=2"))
    message = str(exc)
    assert message.splitlines()[:2] == [
        "Can't play back this request: no recorded interaction matches it (the closest differ in query).",
        "record_mode 'once' doesn't record new requests into an existing cassette.",
    ]
    assert "  GET http://example.com/foo?page=2\n" in message
    assert "  1. GET http://example.com/foo\n     query differs: [('page', '2')] != []" in message
    assert "record_mode='new_episodes'" in message


def test_no_match_with_multiline_matcher_message():
    diff = "--- recorded\n+++ this request\n-a\n+b"
    similar = [(_request(), ["method"], [("body", diff)])]
    message = str(_exception(_cassette(), similar))
    assert "     body differs:\n       --- recorded\n       +++ this request\n       -a\n       +b" in message


def test_no_match_caps_the_number_of_similar_requests():
    similar = [(_request(f"http://example.com/{i}"), ["method"], [("body", "")]) for i in range(200)]
    message = str(_exception(_cassette(recorded=200), similar))
    assert "  3. GET http://example.com/2\n" in message
    assert "  4. " not in message
    assert "  …and 197 more that also differ in body." in message
    assert len(message) < 2000


def test_no_match_groups_the_rest_by_differing_matchers():
    body_only = (_request(), ["method"], [("body", "")])
    path_and_body = (_request(), ["method"], [("path", ""), ("body", "")])
    similar = [body_only] * 5 + [path_and_body] * 2
    message = str(_exception(_cassette(recorded=7), similar))
    assert "  …and 4 more:\n     2 differ in body\n     2 differ in path and body" in message


def test_nothing_similar():
    exc = _exception(_cassette(), [])
    assert exc.reason == "nothing_similar"
    assert "the cassette has nothing similar to it" in str(exc)
    assert "ignore_hosts" in str(exc)


def test_shows_the_body_when_matching_on_it():
    body = b'{"prompt": "' + b"x" * 1000 + b'"}'
    request = _request("http://example.com/api", "POST", body)
    message = str(_exception(_cassette(match_on=[]), [], request))
    assert "body:" not in message

    from vcr.matchers import body as body_matcher

    message = str(_exception(_cassette(match_on=[body_matcher]), [], request))
    assert '  body: {"prompt": "xxx' in message
    assert f"… ({len(body)} characters)" in message


@pytest.mark.parametrize("record_mode", [RecordMode.ONCE, "once"])
def test_record_mode_is_shown_by_value(record_mode):
    message = str(_exception(_cassette(record_mode=record_mode), []))
    assert "  record_mode: once\n" in message
    assert "RecordMode" not in message


def test_get_message_matches_the_exception():
    cassette = _cassette()
    request = _request()
    with mock.patch.object(Cassette, "find_requests_with_most_matches", return_value=[]):
        message = errors.CannotOverwriteExistingCassetteException._get_message(cassette, request)
    assert message == str(_exception(cassette, [], request))
