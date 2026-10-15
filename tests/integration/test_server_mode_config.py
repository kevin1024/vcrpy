"""Server mode: every VCR option keeps working when requests go through the local server."""

import asyncio
import base64
import json
import unittest
from urllib.parse import urlencode
from urllib.request import urlopen

import pytest

import vcr
from vcr.persisters.filesystem import CassetteNotFoundError
from vcr.serializers import jsonserializer
from vcr.unittest import VCRTestCase

from .server_mode_utils import fetch, upstream_server


@pytest.fixture
def upstream():
    with upstream_server() as server:
        yield server


@pytest.fixture
def path(tmpdir):
    return str(tmpdir.join("cassette.yaml"))


def echo(cass, path="/echo", method="GET", body=None, headers=None):
    status, _, payload = fetch(cass, method, path, body=body, headers=headers)
    assert status == 200
    return json.loads(payload)


# Record modes


def test_record_mode_all_always_hits_upstream(path, upstream):
    for _ in range(2):
        with vcr.use_cassette(path, base_url=upstream.url, record_mode="all") as cass:
            echo(cass)
            assert cass.play_count == 0
    assert len(upstream.hits) == 2


def test_record_mode_once_replays_repeated_requests_in_order(path, upstream):
    with vcr.use_cassette(path, base_url=upstream.url) as cass:
        first, second = echo(cass, "/echo?n=1"), echo(cass, "/echo?n=2")
    with vcr.use_cassette(path, base_url=upstream.url) as cass:
        assert echo(cass, "/echo?n=1") == first
        assert echo(cass, "/echo?n=2") == second
        assert cass.all_played
    assert len(upstream.hits) == 2


# Filters


def test_filter_headers_records_filtered_but_forwards_real_value(path, upstream):
    my_vcr = vcr.VCR(base_url=upstream.url, filter_headers=["authorization", ("x-api-key", "REDACTED")])
    with my_vcr.use_cassette(path) as cass:
        seen = echo(cass, headers={"Authorization": "Bearer secret", "X-Api-Key": "key"})
    assert seen["headers"]["Authorization"] == "Bearer secret"
    assert seen["headers"]["X-Api-Key"] == "key"
    assert "Authorization" not in cass.requests[0].headers
    assert cass.requests[0].headers["X-Api-Key"] == "REDACTED"

    # Replays with a different token, headers are not part of match_on.
    with my_vcr.use_cassette(path, record_mode="none") as cass:
        assert echo(cass, headers={"Authorization": "Bearer other"}) == seen


def test_filter_query_parameters(path, upstream):
    my_vcr = vcr.VCR(base_url=upstream.url, filter_query_parameters=["api_key"])
    with my_vcr.use_cassette(path) as cass:
        seen = echo(cass, "/echo?api_key=secret&q=1")
    assert seen["path"] == "/echo?api_key=secret&q=1"
    assert cass.requests[0].uri == upstream.url + "/echo?q=1"
    with my_vcr.use_cassette(path, record_mode="none") as cass:
        assert echo(cass, "/echo?api_key=secret&q=1") == seen


def test_filter_post_data_parameters(path, upstream):
    my_vcr = vcr.VCR(
        base_url=upstream.url,
        filter_post_data_parameters=["password"],
        match_on=["method", "path", "body"],
    )
    form = urlencode({"user": "me", "password": "secret"}).encode()
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    with my_vcr.use_cassette(path) as cass:
        seen = echo(cass, method="POST", body=form, headers=headers)
    assert base64.b64decode(seen["body"]) == form
    assert cass.requests[0].body == b"user=me"
    with my_vcr.use_cassette(path, record_mode="none") as cass:
        assert echo(cass, method="POST", body=form, headers=headers) == seen


def test_before_record_response(path, upstream):
    def scrub(response):
        response["body"]["string"] = response["body"]["string"].replace(b"/echo", b"/scrubbed")
        return response

    with vcr.use_cassette(path, base_url=upstream.url, before_record_response=scrub) as cass:
        # The live response is untouched...
        assert echo(cass)["path"] == "/echo"
    with vcr.use_cassette(path, base_url=upstream.url, before_record_response=scrub) as cass:
        # ...the recorded one is filtered.
        assert echo(cass)["path"] == "/scrubbed"


def test_before_record_request_returning_none_forwards_without_recording(path, upstream):
    def skip_health(request):
        return None if request.path == "/health" else request

    for _ in range(2):
        with vcr.use_cassette(path, base_url=upstream.url, before_record_request=skip_health) as cass:
            echo(cass, "/health")
            echo(cass, "/echo")
    assert [hit[1] for hit in upstream.hits] == ["/health", "/echo", "/health"]
    assert [request.path for request in cass.requests] == ["/echo"]


def test_ignore_localhost_means_forward_but_never_record(path, upstream):
    with vcr.use_cassette(path, base_url=upstream.url, ignore_localhost=True) as cass:
        echo(cass)
        assert len(cass) == 0
    with vcr.use_cassette(
        path,
        base_url=upstream.url,
        ignore_hosts=["127.0.0.1"],
        record_mode="none",
    ) as cass:
        echo(cass)
    assert len(upstream.hits) == 2


# Matching


def test_match_on_and_custom_matcher(path, upstream):
    def same_first_segment(r1, r2):
        assert r1.path.split("/")[1] == r2.path.split("/")[1]

    my_vcr = vcr.VCR(base_url=upstream.url)
    my_vcr.register_matcher("first_segment", same_first_segment)
    with my_vcr.use_cassette(path) as cass:
        recorded = echo(cass, "/echo/a?x=1")
    with my_vcr.use_cassette(path, match_on=["method", "first_segment"], record_mode="none") as cass:
        assert echo(cass, "/echo/b?x=2") == recorded
    assert len(upstream.hits) == 1


def test_allow_playback_repeats(path, upstream):
    with vcr.use_cassette(path, base_url=upstream.url) as cass:
        recorded = echo(cass)
    with vcr.use_cassette(path, base_url=upstream.url, allow_playback_repeats=True) as cass:
        assert [echo(cass) for _ in range(3)] == [recorded] * 3
        assert cass.play_count == 3


def test_drop_unused_requests(path, upstream):
    with vcr.use_cassette(path, base_url=upstream.url) as cass:
        echo(cass, "/echo/used")
        echo(cass, "/echo/unused")
    with vcr.use_cassette(path, base_url=upstream.url, drop_unused_requests=True) as cass:
        echo(cass, "/echo/used")
    with vcr.use_cassette(path, base_url=upstream.url) as cass:
        assert [request.path for request in cass.requests] == ["/echo/used"]


# Persistence


def test_record_on_exception_false(path, upstream):
    with (
        pytest.raises(RuntimeError),
        vcr.use_cassette(path, base_url=upstream.url, record_on_exception=False) as cass,
    ):
        echo(cass)
        raise RuntimeError("boom")
    with vcr.use_cassette(path, base_url=upstream.url) as cass:
        assert len(cass) == 0


def test_record_on_exception_true_and_server_errors_do_not_hide_the_exception(path, upstream):
    with (
        pytest.raises(RuntimeError),
        vcr.use_cassette(path, base_url=upstream.url, record_mode="none") as cass,
    ):
        fetch(cass, "GET", "/not-recorded")
        raise RuntimeError("the test's own exception wins")


def test_custom_serializer_and_persister(upstream):
    store = {}

    class MemoryPersister:
        @staticmethod
        def load_cassette(cassette_path, serializer):
            if cassette_path not in store:
                raise CassetteNotFoundError()
            from vcr.serialize import deserialize

            return deserialize(store[cassette_path], serializer)

        @staticmethod
        def save_cassette(cassette_path, cassette_dict, serializer):
            from vcr.serialize import serialize

            store[cassette_path] = serialize(cassette_dict, serializer)

    my_vcr = vcr.VCR(base_url=upstream.url, serializer="custom-json")
    my_vcr.register_serializer("custom-json", jsonserializer)
    my_vcr.register_persister(MemoryPersister)
    for _ in range(2):
        with my_vcr.use_cassette("in-memory") as cass:
            echo(cass)
    assert cass.play_count == 1
    assert json.loads(store["in-memory"])["interactions"][0]["request"]["uri"] == upstream.url + "/echo"


# Configuration precedence


def test_use_cassette_overrides_vcr_defaults(tmpdir, upstream):
    with upstream_server() as other:
        my_vcr = vcr.VCR(base_url=other.url)
        with my_vcr.use_cassette(str(tmpdir.join("a.yaml")), base_url=upstream.url) as cass:
            echo(cass)
    assert len(upstream.hits) == 1
    assert other.hits == []


def test_base_url_none_disables_server_mode(path, upstream):
    my_vcr = vcr.VCR(base_url=upstream.url)
    with my_vcr.use_cassette(path, base_url=None) as cass:
        assert cass.url is None
        # Back to patch mode: a direct request is recorded.
        urlopen(upstream.url + "/echo").read()
        assert len(cass) == 1


def test_two_cassettes_at_once(tmpdir, upstream):
    with upstream_server() as other:
        with (
            vcr.use_cassette(str(tmpdir.join("a.yaml")), base_url=upstream.url) as a,
            vcr.use_cassette(str(tmpdir.join("b.yaml")), base_url=other.url) as b,
        ):
            assert a.url != b.url
            echo(a, "/echo/a")
            echo(b, "/echo/b")
        assert [hit[1] for hit in other.hits] == ["/echo/b"]
    assert [hit[1] for hit in upstream.hits] == ["/echo/a"]
    assert [request.uri for request in a.requests] == [upstream.url + "/echo/a"]
    assert [request.uri for request in b.requests] == [other.url + "/echo/b"]


def test_server_mode_inside_a_patch_mode_cassette(tmpdir, upstream):
    with (
        vcr.use_cassette(str(tmpdir.join("outer.yaml"))) as outer,
        vcr.use_cassette(str(tmpdir.join("inner.yaml")), base_url=upstream.url) as inner,
    ):
        local_url = inner.url
        echo(inner)
    # The test's own client is patched, so the outer cassette sees the request
    # to the local server, but not the server's request to upstream.
    assert [request.uri for request in outer.requests] == [local_url + "/echo"]
    assert [request.uri for request in inner.requests] == [upstream.url + "/echo"]
    assert len(upstream.hits) == 1


# Decorator forms


def test_decorated_function_with_injected_cassette(path, upstream):
    @vcr.use_cassette(path, base_url=upstream.url, inject_cassette=True)
    def call(cass, suffix):
        return echo(cass, "/echo/" + suffix)

    assert call("x") == call("x")
    assert len(upstream.hits) == 1


def test_decorated_generator(path, upstream):
    @vcr.use_cassette(path, base_url=upstream.url, inject_cassette=True)
    def paths(cass):
        for name in ("a", "b"):
            yield echo(cass, "/echo/" + name)["path"]

    assert list(paths()) == ["/echo/a", "/echo/b"]
    assert list(paths()) == ["/echo/a", "/echo/b"]
    assert len(upstream.hits) == 2


def test_decorated_coroutine(path, upstream):
    @vcr.use_cassette(path, base_url=upstream.url, inject_cassette=True)
    async def call(cass):
        return await asyncio.to_thread(echo, cass)

    assert asyncio.run(call()) == asyncio.run(call())
    assert len(upstream.hits) == 1


def test_vcr_test_case(tmpdir, upstream):
    my_vcr = vcr.VCR(base_url=upstream.url, cassette_library_dir=str(tmpdir), inject_cassette=True)
    results = []

    class Base(my_vcr.test_case()):
        def test_echo(self, cass):
            results.append(echo(cass))

    for _ in range(2):
        Base().test_echo()
    assert len(results) == 2
    assert results[0] == results[1]
    assert len(upstream.hits) == 1


def test_unittest_vcr_test_case(tmpdir, upstream):
    results = []

    class MyTest(VCRTestCase):
        def _get_vcr_kwargs(self, **kwargs):
            return {"base_url": upstream.url, "cassette_library_dir": str(tmpdir)}

        def test_echo(self):
            results.append(echo(self.cassette))

    for _ in range(2):
        result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(MyTest))
        assert result.wasSuccessful()
    assert results[0] == results[1]
    assert len(upstream.hits) == 1
