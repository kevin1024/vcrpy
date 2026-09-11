from pathlib import Path
from unittest import mock

import pytest

from vcr import VCR, mode
from vcr.cassette import Cassette
from vcr.request import Request


@pytest.fixture
def recorded_cassette(tmpdir):
    path = str(tmpdir.join("replace.yml"))
    request = Request("GET", "http://example.com/resource", "", {})
    unused = Request("GET", "http://example.com/unused", "", {})
    with Cassette.use(path=path) as cassette:
        cassette.append(request, "old")
        cassette.append(unused, "unused")
    return path, request


def test_replace_can_be_overridden_by_all(recorded_cassette):
    path, request = recorded_cassette
    with VCR(record_mode=mode.REPLACE).use_cassette(path, record_mode="all") as cassette:
        assert cassette.responses == ["old", "unused"]
        assert not cassette.can_play_response_for(request)
        cassette.append(request, "new")

    assert Cassette.load(path=path).responses == ["old", "unused", "new"]


def test_replace_does_not_load_or_filter_old_interactions():
    request = Request("GET", "http://example.com/resource", "", {})
    persister = mock.Mock()
    persister.load_cassette.side_effect = AssertionError("Existing cassette must not be loaded")
    request_filter = mock.Mock(return_value=request)
    response_filter = mock.Mock(return_value="filtered")
    cassette = Cassette.load(
        path="replace",
        persister=persister,
        record_mode="replace",
        before_record_request=request_filter,
        before_record_response=response_filter,
    )

    persister.load_cassette.assert_not_called()
    request_filter.assert_not_called()
    response_filter.assert_not_called()
    cassette.append(request, "new")
    request_filter.assert_called_once_with(request)
    response_filter.assert_called_once_with("new")
    cassette._save()
    persister.save_cassette.assert_called_once_with(
        "replace",
        {"requests": [request], "responses": ["filtered"]},
        serializer=cassette._serializer,
    )


@pytest.mark.parametrize("filter_name", [None, "before_record_request", "before_record_response"])
def test_replace_saves_empty_cassette(recorded_cassette, filter_name):
    path, request = recorded_cassette
    original = Path(path).read_bytes()
    options = {} if filter_name is None else {filter_name: lambda value: None}
    with VCR(record_mode="replace", **options).use_cassette(path) as cassette:
        if filter_name is not None:
            cassette.append(request, "new")
        assert not cassette.responses
        assert Path(path).read_bytes() == original

    assert not Cassette.load(path=path).responses


@pytest.mark.parametrize("record_on_exception", [False, True])
def test_replace_respects_record_on_exception(recorded_cassette, record_on_exception):
    path, request = recorded_cassette
    original = Path(path).read_bytes()
    recorder = VCR(record_mode="replace", record_on_exception=record_on_exception)
    with (
        pytest.raises(RuntimeError, match="recording failed"),
        recorder.use_cassette(path) as cassette,
    ):
        cassette.append(request, "new")
        raise RuntimeError("recording failed")

    if record_on_exception:
        assert Cassette.load(path=path).responses == ["new"]
    else:
        assert Path(path).read_bytes() == original


@pytest.mark.parametrize("record_response", [False, True])
def test_replace_creates_new_cassette(tmpdir, record_response):
    path = str(tmpdir.join("nested", "replace.yml"))
    with VCR(record_mode="replace").use_cassette(path) as cassette:
        assert not cassette.write_protected
        if record_response:
            cassette.append(Request("GET", "http://example.com/resource", "", {}), "new")
        assert not Path(path).exists()

    assert Path(path).is_file()
    assert Cassette.load(path=path).responses == (["new"] if record_response else [])


def test_replace_decorator_refreshes_each_invocation(recorded_cassette):
    path, request = recorded_cassette

    @VCR(record_mode="replace", inject_cassette=True).use_cassette(path)
    def record(cassette, response):
        assert not cassette.responses
        cassette.append(request, response)

    record("first")
    record("second")
    assert Cassette.load(path=path).responses == ["second"]
