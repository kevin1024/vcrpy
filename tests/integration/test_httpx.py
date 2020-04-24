import pytest
import contextlib
import vcr  # noqa: E402

asyncio = pytest.importorskip("asyncio")
httpx = pytest.importorskip("httpx")


class BaseDoRequest:
    _client_class = None

    def __init__(self, *args, **kwargs):
        self._client = self._client_class(*args, **kwargs)


class DoSyncRequest(BaseDoRequest):
    _client_class = httpx.Client

    def __call__(self, *args, **kwargs):
        return self._client.request(*args, timeout=60, **kwargs)


class DoAsyncRequest(BaseDoRequest):
    _client_class = httpx.AsyncClient

    @staticmethod
    def run_in_loop(coroutine):
        with contextlib.closing(asyncio.new_event_loop()) as loop:
            asyncio.set_event_loop(loop)
            task = loop.create_task(coroutine)
            return loop.run_until_complete(task)

    def __call__(self, *args, **kwargs):
        async def _request():
            async with self._client as c:
                return await c.request(*args, **kwargs)

        return DoAsyncRequest.run_in_loop(_request())


def pytest_generate_tests(metafunc):
    if "do_request" in metafunc.fixturenames:
        metafunc.parametrize("do_request", [DoAsyncRequest, DoSyncRequest])
    if "scheme" in metafunc.fixturenames:
        metafunc.parametrize("scheme", ["http", "https"])


@pytest.fixture
def yml(tmpdir, request):
    return str(tmpdir.join(request.function.__name__ + ".yaml"))


def test_status(tmpdir, scheme, do_request):
    url = scheme + "://httpbin.org"
    with vcr.use_cassette(str(tmpdir.join("status.yaml"))):
        response = do_request()("GET", url)

    with vcr.use_cassette(str(tmpdir.join("status.yaml"))) as cassette:
        cassette_response = do_request()("GET", url)
        assert cassette_response.status_code == response.status_code
        assert cassette.play_count == 1


def test_case_insensitive_headers(tmpdir, scheme, do_request):
    url = scheme + "://httpbin.org"
    with vcr.use_cassette(str(tmpdir.join("whatever.yaml"))):
        do_request()("GET", url)

    with vcr.use_cassette(str(tmpdir.join("whatever.yaml"))) as cassette:
        cassette_response = do_request()("GET", url)
        assert "Content-Type" in cassette_response.headers
        assert "content-type" in cassette_response.headers
        assert cassette.play_count == 1


def test_content(tmpdir, scheme, do_request):
    url = scheme + "://httpbin.org"
    with vcr.use_cassette(str(tmpdir.join("cointent.yaml"))):
        response = do_request()("GET", url)

    with vcr.use_cassette(str(tmpdir.join("cointent.yaml"))) as cassette:
        cassette_response = do_request()("GET", url)
        assert cassette_response.content == response.content
        assert cassette.play_count == 1


def test_json(tmpdir, scheme, do_request):
    url = scheme + "://httpbin.org/get"
    headers = {"Content-Type": "application/json"}

    with vcr.use_cassette(str(tmpdir.join("json.yaml"))):
        response = do_request(headers=headers)("GET", url)

    with vcr.use_cassette(str(tmpdir.join("json.yaml"))) as cassette:
        cassette_response = do_request(headers=headers)("GET", url)
        assert cassette_response.json() == response.json()
        assert cassette.play_count == 1


def test_params_same_url_distinct_params(tmpdir, scheme, do_request):
    url = scheme + "://httpbin.org/get"
    headers = {"Content-Type": "application/json"}
    params = {"a": 1, "b": False, "c": "c"}

    with vcr.use_cassette(str(tmpdir.join("get.yaml"))) as cassette:
        response = do_request()("GET", url, params=params, headers=headers)

    with vcr.use_cassette(str(tmpdir.join("get.yaml"))) as cassette:
        cassette_response = do_request()("GET", url, params=params, headers=headers)
        assert cassette_response.request.url == response.request.url
        assert cassette_response.json() == response.json()
        assert cassette.play_count == 1

    params = {"other": "params"}
    with vcr.use_cassette(str(tmpdir.join("get.yaml"))) as cassette:
        with pytest.raises(vcr.errors.CannotOverwriteExistingCassetteException):
            do_request()("GET", url, params=params, headers=headers)


def test_redirect(tmpdir, do_request, yml):
    url = "https://httpbin.org/redirect/2"

    response = do_request()("GET", url)
    with vcr.use_cassette(yml):
        response = do_request()("GET", url)

    with vcr.use_cassette(yml) as cassette:
        cassette_response = do_request()("GET", url)

        assert cassette_response.status_code == response.status_code
        assert len(cassette_response.history) == len(response.history)
        assert len(cassette) == 3
        assert cassette.play_count == 3

    # Assert that the real response and the cassette response have a similar
    # looking request_info.
    assert cassette_response.request.url == response.request.url
    assert cassette_response.request.method == response.request.method
    assert {k: v for k, v in cassette_response.request.headers.items()} == {
        k: v for k, v in response.request.headers.items()
    }
