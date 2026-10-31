import contextlib
import copy
import functools
import http.client as httplib
import inspect
import os
from typing import ClassVar
from unittest import mock

import pytest
import yaml

from vcr.cassette import Cassette
from vcr.errors import (
    CannotOverwriteExistingCassetteException,
    MissingMetadataError,
    UnhandledHTTPRequestError,
)
from vcr.patch import force_reset
from vcr.persisters.filesystem import CassetteNotFoundError
from vcr.request import Request
from vcr.stubs import VCRHTTPSConnection


def test_cassette_load(tmpdir):
    a_file = tmpdir.join("test_cassette.yml")
    a_file.write(
        yaml.dump(
            {
                "interactions": [
                    {
                        "request": {"body": "", "uri": "foo", "method": "GET", "headers": {}},
                        "response": "bar",
                    },
                ],
            },
        ),
    )
    a_cassette = Cassette.load(path=str(a_file))
    assert len(a_cassette) == 1


def test_cassette_load_nonexistent():
    a_cassette = Cassette.load(path="something/nonexistent.yml")
    assert len(a_cassette) == 0


def test_cassette_load_empty_file(tmpdir):
    a_file = tmpdir.join("empty.yml")
    a_file.write("")
    a_cassette = Cassette.load(path=str(a_file))
    assert len(a_cassette) == 0
    assert not a_cassette.write_protected


def test_cassette_load_invalid_encoding(tmpdir):
    a_file = tmpdir.join("invalid_encoding.yml")
    with open(a_file, "wb") as fd:
        fd.write(b"\xda")
    a_cassette = Cassette.load(path=str(a_file))
    assert len(a_cassette) == 0


def test_cassette_load_invalid_encoding_logs_warning(tmpdir, caplog):
    a_file = tmpdir.join("invalid_encoding.yml")
    with open(a_file, "wb") as fd:
        fd.write(b"\xda")

    with caplog.at_level("WARNING", logger="vcr.cassette"):
        a_cassette = Cassette.load(path=str(a_file))

    assert len(a_cassette) == 0
    assert any("couldn't be loaded" in record.message for record in caplog.records)


def test_cassette_load_nonexistent_does_not_log_warning(caplog):
    with caplog.at_level("WARNING", logger="vcr.cassette"):
        a_cassette = Cassette.load(path="something/nonexistent.yml")

    assert len(a_cassette) == 0
    assert not caplog.records


def test_cassette_not_played():
    a = Cassette("test")
    assert not a.play_count


def test_cassette_append():
    a = Cassette("test")
    a.append("foo", "bar")
    assert a.requests == ["foo"]
    assert a.responses == ["bar"]


def test_cassette_len():
    a = Cassette("test")
    a.append("foo", "bar")
    a.append("foo2", "bar2")
    assert len(a) == 2


def _mock_requests_match(request1, request2, matchers):
    return request1 == request2


@mock.patch("vcr.cassette.requests_match", _mock_requests_match)
def test_cassette_contains():
    a = Cassette("test")
    a.append("foo", "bar")
    assert "foo" in a


@mock.patch("vcr.cassette.requests_match", _mock_requests_match)
def test_cassette_responses_of():
    a = Cassette("test")
    a.append("foo", "bar")
    assert a.responses_of("foo") == ["bar"]


@mock.patch("vcr.cassette.requests_match", _mock_requests_match)
def test_cassette_get_missing_response():
    a = Cassette("test")
    with pytest.raises(UnhandledHTTPRequestError):
        a.responses_of("foo")


@mock.patch("vcr.cassette.requests_match", _mock_requests_match)
def test_cassette_cant_read_same_request_twice():
    a = Cassette("test")
    a.append("foo", "bar")
    a.play_response("foo")
    with pytest.raises(UnhandledHTTPRequestError):
        a.play_response("foo")


def make_get_request():
    conn = httplib.HTTPConnection("www.python.org")
    conn.request("GET", "/index.html")
    return conn.getresponse()


@mock.patch("vcr.cassette.requests_match", return_value=True)
@mock.patch(
    "vcr.cassette.FilesystemPersister.load_cassette",
    classmethod(lambda *args, **kwargs: (("foo",), (mock.MagicMock(),))),
)
@mock.patch("vcr.cassette.Cassette.can_play_response_for", return_value=True)
@mock.patch("vcr.stubs.VCRHTTPResponse")
def test_function_decorated_with_use_cassette_can_be_invoked_multiple_times(*args):
    decorated_function = Cassette.use(path="test")(make_get_request)
    for _ in range(4):
        decorated_function()


def test_arg_getter_functionality():
    arg_getter = mock.Mock(return_value={"path": "test"})
    context_decorator = Cassette.use_arg_getter(arg_getter)

    with context_decorator as cassette:
        assert cassette._path == "test"

    arg_getter.return_value = {"path": "other"}

    with context_decorator as cassette:
        assert cassette._path == "other"

    arg_getter.return_value = {"path": "other", "filter_headers": ("header_name",)}

    @context_decorator
    def function():
        pass

    with mock.patch.object(Cassette, "load", return_value=mock.MagicMock(inject=False)) as cassette_load:
        function()
        cassette_load.assert_called_once_with(**arg_getter.return_value)


def test_cassette_not_all_played():
    a = Cassette("test")
    a.append("foo", "bar")
    assert not a.all_played


@mock.patch("vcr.cassette.requests_match", _mock_requests_match)
def test_cassette_all_played():
    a = Cassette("test")
    a.append("foo", "bar")
    a.play_response("foo")
    assert a.all_played


@mock.patch("vcr.cassette.requests_match", _mock_requests_match)
def test_cassette_allow_playback_repeats():
    a = Cassette("test", allow_playback_repeats=True)
    a.append("foo", "bar")
    a.append("other", "resp")
    for _ in range(10):
        assert a.play_response("foo") == "bar"
    assert a.play_count == 10
    assert a.all_played is False
    assert a.play_response("other") == "resp"
    assert a.play_count == 11
    assert a.all_played

    a.allow_playback_repeats = False
    with pytest.raises(UnhandledHTTPRequestError) as e:
        a.play_response("foo")
    assert str(e.value) == "\"The cassette ('test') doesn't contain the request ('foo') asked for\""
    a.rewind()
    assert a.all_played is False
    assert a.play_response("foo") == "bar"
    assert a.all_played is False
    assert a.play_response("other") == "resp"
    assert a.all_played


@mock.patch("vcr.cassette.requests_match", _mock_requests_match)
def test_cassette_rewound():
    a = Cassette("test")
    a.append("foo", "bar")
    a.play_response("foo")
    assert a.all_played

    a.rewind()
    assert not a.all_played


def test_before_record_response():
    before_record_response = mock.Mock(return_value="mutated")
    cassette = Cassette("test", before_record_response=before_record_response)
    cassette.append("req", "res")

    before_record_response.assert_called_once_with("res")
    assert cassette.responses[0] == "mutated"


def test_before_record_response_is_called_when_loading_existing_cassette(tmpdir):
    file = tmpdir.join("test_cassette.yml")
    file.write(
        yaml.dump(
            {
                "interactions": [
                    {
                        "request": {"body": "", "uri": "foo", "method": "GET", "headers": {}},
                        "response": "bar",
                    },
                ],
            },
        ),
    )

    before_record_response = mock.Mock(return_value="baz")
    cassette = Cassette.load(path=str(file), before_record_response=before_record_response)

    before_record_response.assert_called_once_with("bar")
    assert cassette.responses[0] == "baz"


def assert_get_response_body_is(value):
    conn = httplib.HTTPConnection("www.python.org")
    conn.request("GET", "/index.html")
    assert conn.getresponse().read().decode("utf8") == value


@mock.patch("vcr.cassette.requests_match", _mock_requests_match)
@mock.patch("vcr.cassette.Cassette.can_play_response_for", return_value=True)
@mock.patch("vcr.cassette.Cassette._save", return_value=True)
def test_nesting_cassette_context_managers(*args):
    first_response = {
        "body": {"string": b"first_response"},
        "headers": {},
        "status": {"message": "m", "code": 200},
    }

    second_response = copy.deepcopy(first_response)
    second_response["body"]["string"] = b"second_response"

    with contextlib.ExitStack() as exit_stack:
        first_cassette = exit_stack.enter_context(Cassette.use(path="test"))
        exit_stack.enter_context(
            mock.patch.object(first_cassette, "play_response", return_value=first_response),
        )
        assert_get_response_body_is("first_response")

        # Make sure a second cassette can supersede the first
        with (
            Cassette.use(path="test") as second_cassette,
            mock.patch.object(second_cassette, "play_response", return_value=second_response),
        ):
            assert_get_response_body_is("second_response")

        # Now the first cassette should be back in effect
        assert_get_response_body_is("first_response")


def test_nesting_context_managers_by_checking_references_of_http_connection():
    original = httplib.HTTPConnection
    with Cassette.use(path="test"):
        first_cassette_HTTPConnection = httplib.HTTPConnection
        with Cassette.use(path="test"):
            second_cassette_HTTPConnection = httplib.HTTPConnection
            assert second_cassette_HTTPConnection is not first_cassette_HTTPConnection
            with Cassette.use(path="test"):
                assert httplib.HTTPConnection is not second_cassette_HTTPConnection
                with force_reset():
                    assert httplib.HTTPConnection is original
            assert httplib.HTTPConnection is second_cassette_HTTPConnection
        assert httplib.HTTPConnection is first_cassette_HTTPConnection


def test_custom_patchers():
    class Test:
        attribute = None

    with Cassette.use(path="custom_patches", custom_patches=((Test, "attribute", VCRHTTPSConnection),)):
        assert issubclass(Test.attribute, VCRHTTPSConnection)
        assert VCRHTTPSConnection is not Test.attribute
        old_attribute = Test.attribute

        with Cassette.use(path="custom_patches", custom_patches=((Test, "attribute", VCRHTTPSConnection),)):
            assert issubclass(Test.attribute, VCRHTTPSConnection)
            assert VCRHTTPSConnection is not Test.attribute
            assert Test.attribute is not old_attribute

        assert issubclass(Test.attribute, VCRHTTPSConnection)
        assert VCRHTTPSConnection is not Test.attribute
        assert Test.attribute is old_attribute


def test_decorated_functions_are_reentrant():
    info = {"second": False}
    original_conn = httplib.HTTPConnection

    @Cassette.use(path="whatever", inject=True)
    def test_function(cassette):
        if info["second"]:
            assert httplib.HTTPConnection is not info["first_conn"]
        else:
            info["first_conn"] = httplib.HTTPConnection
            info["second"] = True
            test_function()
            assert httplib.HTTPConnection is info["first_conn"]

    test_function()
    assert httplib.HTTPConnection is original_conn


def test_cassette_use_called_without_path_uses_function_to_generate_path():
    @Cassette.use(inject=True)
    def function_name(cassette):
        assert cassette._path == "function_name"

    function_name()


def test_path_transformer_with_function_path():
    def path_transformer(path):
        return os.path.join("a", path)

    @Cassette.use(inject=True, path_transformer=path_transformer)
    def function_name(cassette):
        assert cassette._path == os.path.join("a", "function_name")

    function_name()


def test_path_transformer_with_context_manager():
    with Cassette.use(path="b", path_transformer=lambda *args: "a") as cassette:
        assert cassette._path == "a"


def test_path_transformer_None():
    with Cassette.use(path="a", path_transformer=None) as cassette:
        assert cassette._path == "a"


def test_func_path_generator():
    def generator(function):
        return os.path.join(os.path.dirname(inspect.getfile(function)), function.__name__)

    @Cassette.use(inject=True, func_path_generator=generator)
    def function_name(cassette):
        assert cassette._path == os.path.join(os.path.dirname(__file__), "function_name")

    function_name()


def test_use_as_decorator_on_coroutine():
    original_http_connection = httplib.HTTPConnection

    @Cassette.use(inject=True)
    def test_function(cassette):
        assert httplib.HTTPConnection.cassette is cassette
        assert httplib.HTTPConnection is not original_http_connection
        value = yield 1
        assert value == 1
        assert httplib.HTTPConnection.cassette is cassette
        assert httplib.HTTPConnection is not original_http_connection
        value = yield 2
        assert value == 2

    coroutine = test_function()
    value = next(coroutine)
    while True:
        try:
            value = coroutine.send(value)
        except StopIteration:
            break


def test_use_as_decorator_on_generator():
    original_http_connection = httplib.HTTPConnection

    @Cassette.use(inject=True)
    def test_function(cassette):
        assert httplib.HTTPConnection.cassette is cassette
        assert httplib.HTTPConnection is not original_http_connection
        yield 1
        assert httplib.HTTPConnection.cassette is cassette
        assert httplib.HTTPConnection is not original_http_connection
        yield 2

    assert list(test_function()) == [1, 2]


@mock.patch("vcr.cassette.get_matchers_results")
def test_find_requests_with_most_matches_one_similar_request(mock_get_matchers_results):
    mock_get_matchers_results.side_effect = [
        (["method"], [("path", "failed : path"), ("query", "failed : query")]),
        (["method", "path"], [("query", "failed : query")]),
        ([], [("method", "failed : method"), ("path", "failed : path"), ("query", "failed : query")]),
    ]

    cassette = Cassette("test")
    for request in range(1, 4):
        cassette.append(request, "response")
    result = cassette.find_requests_with_most_matches("fake request")
    assert result == [(2, ["method", "path"], [("query", "failed : query")])]


@mock.patch("vcr.cassette.get_matchers_results")
def test_find_requests_with_most_matches_no_similar_requests(mock_get_matchers_results):
    mock_get_matchers_results.side_effect = [
        ([], [("path", "failed : path"), ("query", "failed : query")]),
        ([], [("path", "failed : path"), ("query", "failed : query")]),
        ([], [("path", "failed : path"), ("query", "failed : query")]),
    ]

    cassette = Cassette("test")
    for request in range(1, 4):
        cassette.append(request, "response")
    result = cassette.find_requests_with_most_matches("fake request")
    assert result == []


@mock.patch("vcr.cassette.get_matchers_results")
def test_find_requests_with_most_matches_many_similar_requests(mock_get_matchers_results):
    mock_get_matchers_results.side_effect = [
        (["method", "path"], [("query", "failed : query")]),
        (["method"], [("path", "failed : path"), ("query", "failed : query")]),
        (["method", "path"], [("query", "failed : query")]),
    ]

    cassette = Cassette("test")
    for request in range(1, 4):
        cassette.append(request, "response")
    result = cassette.find_requests_with_most_matches("fake request")
    assert result == [
        (1, ["method", "path"], [("query", "failed : query")]),
        (3, ["method", "path"], [("query", "failed : query")]),
    ]


def test_used_interactions(tmpdir):
    interactions = [
        {"request": {"body": "", "uri": "foo1", "method": "GET", "headers": {}}, "response": "bar1"},
        {"request": {"body": "", "uri": "foo2", "method": "GET", "headers": {}}, "response": "bar2"},
        {"request": {"body": "", "uri": "foo3", "method": "GET", "headers": {}}, "response": "bar3"},
    ]
    file = tmpdir.join("test_cassette.yml")
    file.write(yaml.dump({"interactions": [interactions[0], interactions[1]]}))

    cassette = Cassette.load(path=str(file))
    request = Request._from_dict(interactions[1]["request"])
    cassette.play_response(request)
    assert len(cassette._played_interactions) < len(cassette._old_interactions)

    request = Request._from_dict(interactions[2]["request"])
    cassette.append(request, interactions[2]["response"])
    assert len(cassette._new_interactions()) == 1

    used_interactions = cassette._played_interactions + cassette._new_interactions()
    assert len(used_interactions) == 2

    # Also verify that we can account for request modification
    file2 = tmpdir.join("test_cassette2.yml")
    file2.write(yaml.dump({"interactions": [interactions[0]]}))

    def filter_auth_header(request: Request) -> Request:
        request = copy.deepcopy(request)
        if "Authorization" in request.headers:
            del request.headers["Authorization"]
        return request

    # Play response with a raw request that has header to be filtered
    cassette2 = Cassette.load(
        path=str(file2),
        before_record_request=filter_auth_header,
        drop_unused_requests=True,
    )
    cassette2.play_response(
        Request._from_dict(
            {
                "body": "",
                "uri": "foo1",
                "method": "GET",
                "headers": {"Authorization": "Bearer secret-token"},
            },
        ),
    )
    assert len(cassette2._played_interactions) == 1
    played_request, _ = cassette2._played_interactions[0]
    assert "Authorization" not in played_request.headers, "Expected played request's header to be filtered"

    # Save and verify the cassette doesn't contain Authorization
    cassette2._save(force=True)
    with file2.open() as f:
        saved_content = f.read()
    assert "Authorization" not in saved_content
    assert "secret-token" not in saved_content


class _MemoryPersister:
    cassettes: ClassVar[dict] = {}

    @classmethod
    def load_cassette(cls, cassette_path, serializer):
        if cassette_path not in cls.cassettes:
            raise CassetteNotFoundError
        return cls.cassettes[cassette_path]

    @classmethod
    def save_cassette(cls, cassette_path, cassette_dict, serializer):
        cls.cassettes[cassette_path] = (cassette_dict["requests"], cassette_dict["responses"])


def _secret_interaction(secret):
    request = Request(
        "POST",
        f"http://example.com/?key={secret}",
        f"token={secret}",
        {"Authorization": secret},
    )
    response = {
        "status": {"code": 200, "message": "OK"},
        "headers": {"X-Echo": [secret]},
        "body": {"string": f'{{"token": "{secret}"}}'.encode()},
    }
    return request, response


@pytest.mark.parametrize(
    "filter_sensitive_data",
    [
        {"<TOKEN>": "s3cret"},
        [("<TOKEN>", "s3cret")],
        {"<TOKEN>": lambda request, response: "s3cret"},
    ],
)
def test_filter_sensitive_data_hides_on_save_and_restores_on_load(filter_sensitive_data):
    path = f"sensitive-{id(filter_sensitive_data)}"
    cassette = Cassette(path, persister=_MemoryPersister, filter_sensitive_data=filter_sensitive_data)
    cassette.append(*_secret_interaction("s3cret"))
    cassette._save()

    requests, responses = _MemoryPersister.cassettes[path]
    saved = repr([r._to_dict() for r in requests]) + repr(responses)
    assert "s3cret" not in saved
    assert saved.count("<TOKEN>") == 5

    loaded = Cassette.load(path=path, persister=_MemoryPersister, filter_sensitive_data=filter_sensitive_data)
    request, response = loaded.data[0]
    expected_request, expected_response = _secret_interaction("s3cret")
    assert request._to_dict() == expected_request._to_dict()
    assert response == expected_response


def test_filter_sensitive_data_skips_missing_values():
    # e.g. an environment variable that isn't set in CI
    path = "sensitive-missing"
    cassette = Cassette(
        path,
        persister=_MemoryPersister,
        filter_sensitive_data={"<TOKEN>": None, "": "s3cret"},
    )
    cassette.append(*_secret_interaction("s3cret"))
    cassette._save()

    requests, _ = _MemoryPersister.cassettes[path]
    assert requests[0].uri == "http://example.com/?key=s3cret"


def test_filter_sensitive_data_accepts_non_string_values():
    path = "sensitive-port"
    cassette = Cassette(path, persister=_MemoryPersister, filter_sensitive_data={"<PORT>": 8080})
    cassette.append(Request("GET", "http://example.com:8080/", "", {}), {"body": {"string": b"port 8080"}})
    cassette._save()

    requests, responses = _MemoryPersister.cassettes[path]
    assert requests[0].uri == "http://example.com:<PORT>/"
    assert responses[0]["body"]["string"] == b"port <PORT>"


def _hooked_cassette(path, **kwargs):
    return Cassette(path, persister=_MemoryPersister, **kwargs)


def _interaction(uri="http://example.com/", body=b"hello"):
    return Request("GET", uri, "", {}), {"status": {"code": 200, "message": "OK"}, "body": {"string": body}}


def test_before_save_interaction_changes_the_saved_cassette_only():
    def shout(request, response):
        response["body"]["string"] = response["body"]["string"].upper()
        return request, response

    cassette = _hooked_cassette("hooks-save", before_save_interaction=shout)
    cassette.append(*_interaction())
    cassette._save()

    _, responses = _MemoryPersister.cassettes["hooks-save"]
    assert responses[0]["body"]["string"] == b"HELLO"
    # The hook got a copy: the interaction in memory is unchanged.
    assert cassette.data[0][1]["body"]["string"] == b"hello"


def test_before_save_interaction_can_drop_interactions():
    def drop_secret_paths(request, response):
        return None if request.path == "/secret" else (request, response)

    cassette = _hooked_cassette("hooks-drop", before_save_interaction=drop_secret_paths)
    cassette.append(*_interaction("http://example.com/secret"))
    cassette.append(*_interaction("http://example.com/public"))
    cassette._save()

    requests, _ = _MemoryPersister.cassettes["hooks-drop"]
    assert [r.path for r in requests] == ["/public"]


def test_after_load_interaction_changes_and_skips_loaded_interactions():
    _MemoryPersister.cassettes["hooks-load"] = (
        [_interaction("http://example.com/a")[0], _interaction("http://example.com/b")[0]],
        [_interaction()[1], _interaction()[1]],
    )

    def hooks(request, response):
        if request.path == "/b":
            return None
        response["body"]["string"] = b"changed"
        return request, response

    cassette = Cassette.load(path="hooks-load", persister=_MemoryPersister, after_load_interaction=hooks)
    assert [(r.path, resp["body"]["string"]) for r, resp in cassette.data] == [("/a", b"changed")]


def test_interaction_hooks_run_in_order():
    calls = []

    def hook(name):
        def run(request, response):
            calls.append(name)
            return request, response

        return run

    cassette = _hooked_cassette("hooks-order", before_save_interaction=[hook("first"), hook("second")])
    cassette.append(*_interaction())
    cassette._save()
    assert calls == ["first", "second"]


def test_interaction_hooks_see_real_values_around_filter_sensitive_data():
    seen = {}

    def on_save(request, response):
        seen["save"] = request.uri
        return request, response

    def on_load(request, response):
        seen["load"] = request.uri
        return request, response

    options = {
        "filter_sensitive_data": {"<KEY>": "s3cret"},
        "before_save_interaction": on_save,
        "after_load_interaction": on_load,
    }
    cassette = _hooked_cassette("hooks-sensitive", **options)
    cassette.append(*_interaction("http://example.com/?key=s3cret"))
    cassette._save()
    Cassette.load(path="hooks-sensitive", persister=_MemoryPersister, **options)

    assert _MemoryPersister.cassettes["hooks-sensitive"][0][0].uri == "http://example.com/?key=<KEY>"
    assert seen == {"save": "http://example.com/?key=s3cret", "load": "http://example.com/?key=s3cret"}


def test_interaction_hooks_can_take_the_cassette():
    seen = []

    def with_cassette(request, response, cassette):
        seen.append(("save", cassette.path))
        return request, response

    def with_args(*args):
        seen.append(("args", len(args)))
        return args[:2]

    class Hook:
        def __call__(self, request, response):
            seen.append(("callable", None))
            return request, response

    def with_prefix(prefix, request, response):
        seen.append((prefix, None))
        return request, response

    hooks = [with_cassette, with_args, Hook(), functools.partial(with_prefix, "partial")]
    cassette = _hooked_cassette("hooks-cassette", before_save_interaction=hooks)
    cassette.append(*_interaction())
    cassette._save()

    assert seen == [("save", "hooks-cassette"), ("args", 3), ("callable", None), ("partial", None)]


def test_cassette_path():
    assert Cassette("path/to/cassette.yaml").path == "path/to/cassette.yaml"


def test_interaction_hook_with_wrong_return_value():
    def returns_only_the_response(request, response):
        return response

    cassette = _hooked_cassette("hooks-wrong-return", before_save_interaction=returns_only_the_response)
    cassette.append(*_interaction())
    with pytest.raises(
        TypeError,
        match=r"returns_only_the_response must return \(request, response\) or None, not dict",
    ):
        cassette._save()


def test_interaction_hooks_accept_a_tuple():
    calls = []

    def hook(request, response):
        calls.append(request.path)
        return request, response

    cassette = _hooked_cassette("hooks-tuple", before_save_interaction=(hook, hook))
    cassette.append(*_interaction())
    cassette._save()
    assert calls == ["/", "/"]


def test_drop_unused_requests_saves_repeated_interactions_once(tmpdir):
    interactions = [
        {"request": {"body": "", "uri": "foo1", "method": "GET", "headers": {}}, "response": "bar1"},
        {"request": {"body": "", "uri": "foo2", "method": "GET", "headers": {}}, "response": "bar2"},
    ]
    file = tmpdir.join("test_cassette.yml")
    file.write(yaml.dump({"interactions": interactions}))

    cassette = Cassette.load(path=str(file), allow_playback_repeats=True, drop_unused_requests=True)
    request = Request._from_dict(interactions[0]["request"])
    cassette.play_response(request)
    cassette.play_response(request)
    cassette._save()

    saved = yaml.safe_load(file.read())["interactions"]
    assert [interaction["request"]["uri"] for interaction in saved] == ["foo1"]


def test_allow_playback_repeats_while_recording():
    cassette = Cassette("test", allow_playback_repeats=True)
    request = Request("GET", "http://example.com/", "", {})
    assert not cassette.can_play_response_for(request)

    cassette.append(request, "response")
    assert cassette.can_play_response_for(request)
    assert cassette.play_response(request) == "response"
    assert len(cassette) == 1


def test_no_playback_while_recording_without_repeats():
    cassette = Cassette("test")
    request = Request("GET", "http://example.com/", "", {})
    cassette.append(request, "response")
    assert not cassette.can_play_response_for(request)


def test_metadata_write(tmpdir):
    file = tmpdir.join("test_cassette.yml")
    cassette = Cassette(path=str(file))

    assert cassette.get_metadata("key", "value") == "value"
    assert cassette.get_metadata("key", "default") == "value"
    assert cassette.get_metadata("otherkey", "othervalue") == "othervalue"

    cassette._save()
    assert yaml.safe_load(file.read())["metadata"] == {"key": "value", "otherkey": "othervalue"}


def test_no_metadata_is_not_saved(tmpdir):
    file = tmpdir.join("test_cassette.yml")
    cassette = Cassette(path=str(file))
    cassette.append(Request("GET", "http://example.com/", "", {}), "response")
    cassette._save()
    assert "metadata" not in yaml.safe_load(file.read())


def _cassette_with_metadata(tmpdir):
    file = tmpdir.join("test_cassette.yml")
    file.write(
        yaml.dump(
            {
                "interactions": [
                    {
                        "request": {"body": "", "uri": "foo1", "method": "GET", "headers": {}},
                        "response": "bar1",
                    },
                ],
                "metadata": {"key": "value"},
            },
        ),
    )
    return file


def test_metadata_load(tmpdir):
    file = _cassette_with_metadata(tmpdir)
    cassette = Cassette.load(path=str(file))
    assert cassette.get_metadata("key", "default") == "value"

    with pytest.raises(MissingMetadataError) as excinfo:
        cassette.get_metadata("otherkey", "default")
    # It's a CannotOverwriteExistingCassetteException, so code that catches those catches it too.
    assert isinstance(excinfo.value, CannotOverwriteExistingCassetteException)
    assert excinfo.value.key == "otherkey"
    assert excinfo.value.reason == "missing_metadata"
    assert "'otherkey'" in str(excinfo.value)


@pytest.mark.parametrize(
    "options",
    [{"record_mode": "new_episodes"}, {"record_mode": "all"}, {"drop_unused_requests": True}],
)
def test_metadata_kept_and_added(tmpdir, options):
    file = _cassette_with_metadata(tmpdir)
    cassette = Cassette.load(path=str(file), **options)
    assert cassette.get_metadata("key", "default") == "value"
    if options.get("record_mode") == "new_episodes":
        assert cassette.get_metadata("otherkey", "othervalue") == "othervalue"
    cassette._save(force=True)

    expected = {"key": "value"}
    if options.get("record_mode") == "new_episodes":
        expected["otherkey"] = "othervalue"
    assert yaml.safe_load(file.read())["metadata"] == expected


def test_metadata_with_persister_without_metadata():
    # Persisters written before metadata return (requests, responses).
    path = "no-metadata"
    _MemoryPersister.cassettes[path] = ([Request("GET", "http://example.com/", "", {})], ["response"])
    cassette = Cassette.load(path=path, persister=_MemoryPersister, record_mode="new_episodes")
    assert len(cassette) == 1
    assert cassette.get_metadata("key", "value") == "value"
