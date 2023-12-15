import pytest

import vcr

asyncio = pytest.importorskip("asyncio")
httpx = pytest.importorskip("httpx")


@pytest.fixture(params=["https", "http"])
def scheme(request):
    """Fixture that returns both http and https."""
    return request.param


class BaseDoRequest:
    _client_class = None

    def __init__(self, *args, **kwargs):
        self._client_args = args
        self._client_kwargs = kwargs
        self._client_kwargs["follow_redirects"] = self._client_kwargs.get("follow_redirects", True)

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

    def stream(self, *args, **kwargs):
        with self.client.stream(*args, **kwargs) as response:
            return b"".join(response.iter_bytes())


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
        except AttributeError as e:
            raise ValueError('To access async client, use "with do_request() as client"') from e

    def __call__(self, *args, **kwargs):
        if hasattr(self, "_loop"):
            return self._loop.run_until_complete(self.client.request(*args, **kwargs))

        # Use one-time context and dispose of the loop/client afterwards
        with self:
            return self._loop.run_until_complete(self.client.request(*args, **kwargs))

    async def _get_stream(self, *args, **kwargs):
        async with self.client.stream(*args, **kwargs) as response:
            content = b""
            async for c in response.aiter_bytes():
                content += c
        return content

    def stream(self, *args, **kwargs):
        if hasattr(self, "_loop"):
            return self._loop.run_until_complete(self._get_stream(*args, **kwargs))

        # Use one-time context and dispose of the loop/client afterwards
        with self:
            return self._loop.run_until_complete(self._get_stream(*args, **kwargs))


def pytest_generate_tests(metafunc):
    if "do_request" in metafunc.fixturenames:
        metafunc.parametrize("do_request", [DoAsyncRequest, DoSyncRequest])


@pytest.fixture
def yml(tmpdir, request):
    return str(tmpdir.join(request.function.__name__ + ".yaml"))


@pytest.mark.online
def test_status(tmpdir, httpbin, do_request):
    url = httpbin.url

    with vcr.use_cassette(str(tmpdir.join("status.yaml"))):
        response = do_request()("GET", url)

    with vcr.use_cassette(str(tmpdir.join("status.yaml"))) as cassette:
        cassette_response = do_request()("GET", url)
        assert cassette_response.status_code == response.status_code
        assert cassette.play_count == 1


@pytest.mark.online
def test_case_insensitive_headers(tmpdir, httpbin, do_request):
    url = httpbin.url

    with vcr.use_cassette(str(tmpdir.join("whatever.yaml"))):
        do_request()("GET", url)

    with vcr.use_cassette(str(tmpdir.join("whatever.yaml"))) as cassette:
        cassette_response = do_request()("GET", url)
        assert "Content-Type" in cassette_response.headers
        assert "content-type" in cassette_response.headers
        assert cassette.play_count == 1


@pytest.mark.online
def test_content(tmpdir, httpbin, do_request):
    url = httpbin.url

    with vcr.use_cassette(str(tmpdir.join("cointent.yaml"))):
        response = do_request()("GET", url)

    with vcr.use_cassette(str(tmpdir.join("cointent.yaml"))) as cassette:
        cassette_response = do_request()("GET", url)
        assert cassette_response.content == response.content
        assert cassette.play_count == 1


@pytest.mark.online
def test_json(tmpdir, httpbin, do_request):
    url = httpbin.url + "/json"

    with vcr.use_cassette(str(tmpdir.join("json.yaml"))):
        response = do_request()("GET", url)

    with vcr.use_cassette(str(tmpdir.join("json.yaml"))) as cassette:
        cassette_response = do_request()("GET", url)
        assert cassette_response.json() == response.json()
        assert cassette.play_count == 1


@pytest.mark.online
def test_params_same_url_distinct_params(tmpdir, httpbin, do_request):
    url = httpbin.url + "/get"
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


@pytest.mark.online
def test_redirect(httpbin, yml, do_request):
    url = httpbin.url + "/redirect-to"

    response = do_request()("GET", url)
    with vcr.use_cassette(yml):
        response = do_request()("GET", url, params={"url": "./get", "status_code": 302})

    with vcr.use_cassette(yml) as cassette:
        cassette_response = do_request()("GET", url, params={"url": "./get", "status_code": 302})

        assert cassette_response.status_code == response.status_code
        assert len(cassette_response.history) == len(response.history)
        assert len(cassette) == 2
        assert cassette.play_count == 2

    # Assert that the real response and the cassette response have a similar
    # looking request_info.
    assert cassette_response.request.url == response.request.url
    assert cassette_response.request.method == response.request.method
    assert cassette_response.request.headers.items() == response.request.headers.items()


@pytest.mark.online
def test_work_with_gzipped_data(httpbin, do_request, yml):
    url = httpbin.url + "/gzip?foo=bar"
    headers = {"accept-encoding": "deflate, gzip"}

    with vcr.use_cassette(yml):
        do_request(headers=headers)("GET", url)

    with vcr.use_cassette(yml) as cassette:
        cassette_response = do_request(headers=headers)("GET", url)

        assert cassette_response.headers["content-encoding"] == "gzip"
        assert cassette_response.read()
        assert cassette.play_count == 1


@pytest.mark.online
@pytest.mark.parametrize("url", ["https://github.com/kevin1024/vcrpy/issues/" + str(i) for i in range(3, 6)])
def test_simple_fetching(do_request, yml, url):
    with vcr.use_cassette(yml):
        do_request()("GET", url)

    with vcr.use_cassette(yml) as cassette:
        cassette_response = do_request()("GET", url)
        assert str(cassette_response.request.url) == url
        assert cassette.play_count == 1


@pytest.mark.online
def test_cookies(tmpdir, httpbin, do_request):
    def client_cookies(client):
        return list(client.client.cookies)

    def response_cookies(response):
        return list(response.cookies)

    url = httpbin.url + "/cookies/set"
    params = {"k1": "v1", "k2": "v2"}

    with do_request(params=params, follow_redirects=False) as client:
        assert client_cookies(client) == []

        testfile = str(tmpdir.join("cookies.yml"))
        with vcr.use_cassette(testfile):
            r1 = client("GET", url)

            assert response_cookies(r1) == ["k1", "k2"]

            r2 = client("GET", url)

            assert response_cookies(r2) == ["k1", "k2"]
            assert client_cookies(client) == ["k1", "k2"]

    with do_request(params=params, follow_redirects=False) as new_client:
        assert client_cookies(new_client) == []

        with vcr.use_cassette(testfile) as cassette:
            cassette_response = new_client("GET", url)

            assert cassette.play_count == 1
            assert response_cookies(cassette_response) == ["k1", "k2"]
            assert client_cookies(new_client) == ["k1", "k2"]


@pytest.mark.online
def test_stream(tmpdir, httpbin, do_request):
    url = httpbin.url + "/stream-bytes/512"
    testfile = str(tmpdir.join("stream.yml"))

    with vcr.use_cassette(testfile):
        response_content = do_request().stream("GET", url)
        assert len(response_content) == 512

    with vcr.use_cassette(testfile) as cassette:
        cassette_content = do_request().stream("GET", url)
        assert cassette_content == response_content
        assert len(cassette_content) == 512
        assert cassette.play_count == 1


@pytest.mark.online
def test_text_content_type(tmpdir, httpbin, do_request):
    url = httpbin.url + "/json"

    with vcr.use_cassette(str(tmpdir.join("json_type.yaml"))):
        response = do_request()("GET", url)

    with vcr.use_cassette(str(tmpdir.join("json_type.yaml"))) as cassette:
        cassette_response = do_request()("GET", url)
        assert cassette_response.content == response.content
        assert cassette.play_count == 1
        assert isinstance(cassette.responses[0]["content"], str)


@pytest.mark.online
def test_binary_content_type(tmpdir, httpbin, do_request):
    url = httpbin.url + "/bytes/1024"

    with vcr.use_cassette(str(tmpdir.join("json_type.yaml"))):
        response = do_request()("GET", url)

    with vcr.use_cassette(str(tmpdir.join("json_type.yaml"))) as cassette:
        cassette_response = do_request()("GET", url)
        assert cassette_response.content == response.content
        assert cassette.play_count == 1
        assert isinstance(cassette.responses[0]["content"], bytes)
