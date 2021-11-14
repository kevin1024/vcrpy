import pytest
import os

asyncio = pytest.importorskip("asyncio")
httpx = pytest.importorskip("httpx")

import vcr  # noqa: E402
from vcr.stubs.httpx_stubs import HTTPX_REDIRECT_PARAM  # noqa: E402


class BaseDoRequest:
    _client_class = None

    def __init__(self, *args, **kwargs):
        self._client_args = args
        self._client_kwargs = kwargs

    def _make_client(self):
        return self._client_class(*self._client_args, **self._client_kwargs)


class DoSyncRequest(BaseDoRequest):
    _client_class = httpx.Client

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    @property
    def client(self):
        try:
            return self._client
        except AttributeError:
            self._client = self._make_client()
            return self._client

    def __call__(self, *args, **kwargs):
        return self.client.request(*args, timeout=60, **kwargs)


class DoAsyncRequest(BaseDoRequest):
    _client_class = httpx.AsyncClient

    def __enter__(self):
        # Need to manage both loop and client, because client's implementation
        # will fail if the loop is closed before the client's end of life.
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._client = self._make_client()
        self._loop.run_until_complete(self._client.__aenter__())
        return self

    def __exit__(self, *args):
        try:
            self._loop.run_until_complete(self._client.__aexit__(*args))
        finally:
            del self._client
            self._loop.close()
            del self._loop

    @property
    def client(self):
        try:
            return self._client
        except AttributeError:
            raise ValueError('To access async client, use "with do_request() as client"')

    def __call__(self, *args, **kwargs):
        if hasattr(self, "_loop"):
            return self._loop.run_until_complete(self.client.request(*args, **kwargs))

        # Use one-time context and dispose of the loop/client afterwards
        with self:
            return self(*args, **kwargs)


def pytest_generate_tests(metafunc):
    if "do_request" in metafunc.fixturenames:
        metafunc.parametrize("do_request", [DoAsyncRequest, DoSyncRequest])
    if "scheme" in metafunc.fixturenames:
        metafunc.parametrize("scheme", ["http", "https"])


@pytest.fixture
def yml(tmpdir, request):
    return str(tmpdir.join(request.function.__name__ + ".yaml"))


def test_status(tmpdir, scheme, do_request):
    url = scheme + "://mockbin.org/request"
    with vcr.use_cassette(str(tmpdir.join("status.yaml"))):
        response = do_request()("GET", url)

    with vcr.use_cassette(str(tmpdir.join("status.yaml"))) as cassette:
        cassette_response = do_request()("GET", url)
        assert cassette_response.status_code == response.status_code
        assert cassette.play_count == 1


def test_case_insensitive_headers(tmpdir, scheme, do_request):
    url = scheme + "://mockbin.org/request"
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
    url = "https://mockbin.org/redirect/303/2"

    redirect_kwargs = {HTTPX_REDIRECT_PARAM.name: True}

    response = do_request()("GET", url, **redirect_kwargs)
    with vcr.use_cassette(yml):
        response = do_request()("GET", url, **redirect_kwargs)

    with vcr.use_cassette(yml) as cassette:
        cassette_response = do_request()("GET", url, **redirect_kwargs)

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


def test_work_with_gzipped_data(tmpdir, do_request, yml):
    with vcr.use_cassette(yml):
        do_request()("GET", "https://httpbin.org/gzip")

    with vcr.use_cassette(yml) as cassette:
        cassette_response = do_request()("GET", "https://httpbin.org/gzip")

        assert "gzip" in cassette_response.json()["headers"]["Accept-Encoding"]
        assert cassette_response.read()
        assert cassette.play_count == 1


@pytest.mark.parametrize("url", ["https://github.com/kevin1024/vcrpy/issues/" + str(i) for i in range(3, 6)])
def test_simple_fetching(tmpdir, do_request, yml, url):
    with vcr.use_cassette(yml):
        do_request()("GET", url)

    with vcr.use_cassette(yml) as cassette:
        cassette_response = do_request()("GET", url)
        assert str(cassette_response.request.url) == url
        assert cassette.play_count == 1


def test_behind_proxy(do_request):
    # This is recorded because otherwise we should have a live proxy somewhere.
    yml = (
        os.path.dirname(os.path.realpath(__file__)) + "/cassettes/" + "test_httpx_test_test_behind_proxy.yml"
    )
    url = "https://httpbin.org/headers"
    proxy = "http://localhost:8080"
    proxies = {"http://": proxy, "https://": proxy}

    with vcr.use_cassette(yml):
        response = do_request(proxies=proxies, verify=False)("GET", url)

    with vcr.use_cassette(yml) as cassette:
        cassette_response = do_request(proxies=proxies, verify=False)("GET", url)
        assert str(cassette_response.request.url) == url
        assert cassette.play_count == 1

        assert cassette_response.headers["Via"] == "my_own_proxy", str(cassette_response.headers)
        assert cassette_response.request.url == response.request.url


def test_cookies(tmpdir, scheme, do_request):
    def client_cookies(client):
        return [c for c in client.client.cookies]

    def response_cookies(response):
        return [c for c in response.cookies]

    with do_request() as client:
        assert client_cookies(client) == []

        redirect_kwargs = {HTTPX_REDIRECT_PARAM.name: True}

        url = scheme + "://httpbin.org"
        testfile = str(tmpdir.join("cookies.yml"))
        with vcr.use_cassette(testfile):
            r1 = client("GET", url + "/cookies/set?k1=v1&k2=v2", **redirect_kwargs)
            assert response_cookies(r1.history[0]) == ["k1", "k2"]
            assert response_cookies(r1) == []

            r2 = client("GET", url + "/cookies", **redirect_kwargs)
            assert len(r2.json()["cookies"]) == 2

            assert client_cookies(client) == ["k1", "k2"]

    with do_request() as new_client:
        assert client_cookies(new_client) == []

        with vcr.use_cassette(testfile) as cassette:
            cassette_response = new_client("GET", url + "/cookies/set?k1=v1&k2=v2")
            assert response_cookies(cassette_response.history[0]) == ["k1", "k2"]
            assert response_cookies(cassette_response) == []

            assert cassette.play_count == 2
            assert client_cookies(new_client) == ["k1", "k2"]


def test_relative_redirects(tmpdir, scheme, do_request):
    redirect_kwargs = {HTTPX_REDIRECT_PARAM.name: True}

    url = scheme + "://mockbin.com/redirect/301?to=/redirect/301?to=/request"
    testfile = str(tmpdir.join("relative_redirects.yml"))
    with vcr.use_cassette(testfile):
        response = do_request()("GET", url, **redirect_kwargs)
        assert len(response.history) == 2, response
        assert response.json()["url"].endswith("request")

    with vcr.use_cassette(testfile) as cassette:
        response = do_request()("GET", url, **redirect_kwargs)
        assert len(response.history) == 2
        assert response.json()["url"].endswith("request")

        assert cassette.play_count == 3


def test_redirect_wo_allow_redirects(do_request, yml):
    url = "https://mockbin.org/redirect/308/5"

    redirect_kwargs = {HTTPX_REDIRECT_PARAM.name: False}

    with vcr.use_cassette(yml):
        response = do_request()("GET", url, **redirect_kwargs)

        assert str(response.url).endswith("308/5")
        assert response.status_code == 308

    with vcr.use_cassette(yml) as cassette:
        response = do_request()("GET", url, **redirect_kwargs)

        assert str(response.url).endswith("308/5")
        assert response.status_code == 308

        assert cassette.play_count == 1
