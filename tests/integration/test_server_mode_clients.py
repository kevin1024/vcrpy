"""Server mode with real HTTP client libraries.

Nothing is patched: each client simply talks to ``cass.url``. Every scenario runs
for every installed client through a small adapter with a common interface.
"""

import asyncio
import importlib.util
import io
import json

import pytest

import vcr
from vcr.errors import CannotOverwriteExistingCassetteException
from vcr.server import ERROR_STATUS

from .server_mode_utils import upstream_server


class Response:
    def __init__(self, status, headers, body):
        self.status = status
        self.headers = {key.lower(): value for key, value in headers}
        self.body = body

    def json(self):
        return json.loads(self.body)


class SyncAdapter:
    """``open()`` starts a session (cookies, pooled connections), ``request()`` uses it."""

    supports_cookies = True

    def open(self):
        pass

    def close(self):
        pass


class AsyncAdapter(SyncAdapter):
    """Runs a client coroutine API on a private event loop."""

    def open(self):
        self.loop = asyncio.new_event_loop()
        self.loop.run_until_complete(self.aopen())

    def close(self):
        self.loop.run_until_complete(self.aclose())
        self.loop.close()

    def request(self, method, url, body=None, headers=None):
        return self.loop.run_until_complete(self.arequest(method, url, body, headers or {}))

    async def aopen(self):
        pass

    async def aclose(self):
        pass


class RequestsAdapter(SyncAdapter):
    def open(self):
        import requests

        self.session = requests.Session()

    def close(self):
        self.session.close()

    def request(self, method, url, body=None, headers=None):
        response = self.session.request(method, url, data=body, headers=headers)
        return Response(response.status_code, response.headers.items(), response.content)


class Urllib3Adapter(SyncAdapter):
    supports_cookies = False

    def open(self):
        import urllib3

        self.pool = urllib3.PoolManager()

    def close(self):
        self.pool.clear()

    def request(self, method, url, body=None, headers=None):
        # Default retries: follows redirects, never retries on status codes.
        response = self.pool.request(method, url, body=body, headers=headers)
        return Response(response.status, response.headers.items(), response.data)


class Httplib2Adapter(SyncAdapter):
    supports_cookies = False

    def open(self):
        import httplib2

        self.http = httplib2.Http()

    def close(self):
        self.http.close()

    def request(self, method, url, body=None, headers=None):
        response, content = self.http.request(url, method, body=body, headers=headers)
        headers = [(key, value) for key, value in response.items() if not key.startswith("-")]
        return Response(response.status, headers, content)


class HttpxAdapter(SyncAdapter):
    def open(self):
        import httpx

        self.client = httpx.Client(follow_redirects=True)

    def close(self):
        self.client.close()

    def request(self, method, url, body=None, headers=None):
        response = self.client.request(method, url, content=body, headers=headers)
        return Response(response.status_code, response.headers.items(), response.content)


class HttpxAsyncAdapter(AsyncAdapter):
    async def aopen(self):
        import httpx

        self.client = httpx.AsyncClient(follow_redirects=True)

    async def aclose(self):
        await self.client.aclose()

    async def arequest(self, method, url, body, headers):
        response = await self.client.request(method, url, content=body, headers=headers)
        return Response(response.status_code, response.headers.items(), response.content)


class AiohttpAdapter(AsyncAdapter):
    async def aopen(self):
        import aiohttp

        # aiohttp's default jar ignores cookies set by IP-address hosts such as 127.0.0.1.
        self.session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))

    async def aclose(self):
        await self.session.close()

    async def arequest(self, method, url, body, headers):
        async with self.session.request(method, url, data=body, headers=headers) as response:
            return Response(response.status, response.headers.items(), await response.read())


class TornadoAdapter(AsyncAdapter):
    supports_cookies = False

    async def aopen(self):
        from tornado.httpclient import AsyncHTTPClient

        self.client = AsyncHTTPClient(force_instance=True)

    async def aclose(self):
        self.client.close()

    async def arequest(self, method, url, body, headers):
        if body is None and method in ("POST", "PUT", "PATCH"):
            body = b""
        response = await self.client.fetch(url, method=method, body=body, headers=headers, raise_error=False)
        return Response(response.code, response.headers.get_all(), response.body or b"")


class NiquestsAdapter(SyncAdapter):
    def open(self):
        import niquests

        self.session = niquests.Session()

    def close(self):
        self.session.close()

    def request(self, method, url, body=None, headers=None):
        response = self.session.request(method, url, data=body, headers=headers)
        return Response(response.status_code, response.headers.items(), response.content or b"")


class PycurlAdapter(SyncAdapter):
    def open(self):
        import pycurl

        self.pycurl = pycurl
        self.curl = pycurl.Curl()
        # Enables curl's in-memory cookie engine for this handle.
        self.curl.setopt(pycurl.COOKIEFILE, "")

    def close(self):
        self.curl.close()

    def request(self, method, url, body=None, headers=None):
        pycurl, curl = self.pycurl, self.curl
        buffer = io.BytesIO()
        header_lines = []
        curl.setopt(pycurl.URL, url)
        curl.setopt(pycurl.CUSTOMREQUEST, method)
        curl.setopt(pycurl.FOLLOWLOCATION, True)
        curl.setopt(pycurl.ACCEPT_ENCODING, "")
        curl.setopt(pycurl.HTTPHEADER, [f"{key}: {value}" for key, value in (headers or {}).items()])
        curl.setopt(pycurl.WRITEDATA, buffer)
        curl.setopt(pycurl.HEADERFUNCTION, header_lines.append)
        if body is not None:
            curl.setopt(pycurl.POSTFIELDS, body)
        else:
            curl.setopt(pycurl.HTTPGET, True)
            curl.setopt(pycurl.CUSTOMREQUEST, method)
        curl.perform()
        # With redirects curl reports every header block; keep the last one.
        block = []
        for raw in header_lines:
            line = raw.decode("iso-8859-1").strip()
            if line.startswith("HTTP/"):
                block = []
            elif ":" in line:
                key, value = line.split(":", 1)
                block.append((key.strip(), value.strip()))
        return Response(curl.getinfo(pycurl.RESPONSE_CODE), block, buffer.getvalue())


CLIENTS = {
    "requests": ("requests", RequestsAdapter),
    "urllib3": ("urllib3", Urllib3Adapter),
    "httplib2": ("httplib2", Httplib2Adapter),
    "httpx": ("httpx", HttpxAdapter),
    "httpx-async": ("httpx", HttpxAsyncAdapter),
    "aiohttp": ("aiohttp", AiohttpAdapter),
    "tornado": ("tornado", TornadoAdapter),
    "niquests": ("niquests", NiquestsAdapter),
    "pycurl": ("pycurl", PycurlAdapter),
}


@pytest.fixture(params=sorted(CLIENTS))
def client(request):
    module, adapter_class = CLIENTS[request.param]
    if importlib.util.find_spec(module) is None:
        pytest.skip(f"{module} is not installed")
    adapter = adapter_class()
    adapter.name = request.param
    return adapter


@pytest.fixture
def upstream():
    with upstream_server() as server:
        yield server


@pytest.fixture
def path(tmpdir):
    return str(tmpdir.join("cassette.yaml"))


def record_and_replay(path, upstream, client, action, **cassette_kwargs):
    """Run ``action(client, cass)`` while recording, then while replaying with record_mode=none."""
    results = []
    for record_mode in ("once", "none"):
        hits = len(upstream.hits)
        client.open()
        try:
            with vcr.use_cassette(
                path,
                base_url=upstream.url,
                record_mode=record_mode,
                **cassette_kwargs,
            ) as cass:
                results.append(action(client, cass))
        finally:
            client.close()
        if record_mode == "none":
            assert cass.all_played
            assert len(upstream.hits) == hits, "replay must not reach upstream"
    return results


def test_get_with_query(path, upstream, client):
    def action(client, cass):
        response = client.request("GET", cass.url + "/echo?q=1&lang=en")
        return response.status, response.json()["path"]

    recorded, replayed = record_and_replay(path, upstream, client, action)
    assert recorded == replayed == (200, "/echo?q=1&lang=en")


def test_post_body(path, upstream, client):
    def action(client, cass):
        response = client.request(
            "POST",
            cass.url + "/echo",
            body=b'{"name": "vcr"}',
            headers={"Content-Type": "application/json"},
        )
        return response.json()["method"], response.json()["body"]

    recorded, replayed = record_and_replay(
        path,
        upstream,
        client,
        action,
        match_on=["method", "path", "body"],
    )
    assert recorded == replayed == ("POST", "eyJuYW1lIjogInZjciJ9")


def test_follows_redirects_through_the_local_server(path, upstream, client):
    def action(client, cass):
        return client.request("GET", cass.url + "/redirect").json()["path"]

    recorded, replayed = record_and_replay(path, upstream, client, action)
    assert recorded == replayed == "/echo?redirected=1"


def test_transparent_decompression(path, upstream, client):
    def action(client, cass):
        return client.request("GET", cass.url + "/gzip", headers={"Accept-Encoding": "gzip"}).body

    recorded, replayed = record_and_replay(path, upstream, client, action)
    assert recorded == replayed == b"compressed payload"


def test_error_status_is_a_normal_response(path, upstream, client):
    def action(client, cass):
        return client.request("GET", cass.url + "/status/404").status

    recorded, replayed = record_and_replay(path, upstream, client, action)
    assert recorded == replayed == 404


def test_cookies_in_a_session(path, upstream, client):
    if not client.supports_cookies:
        pytest.skip(f"{client.name} has no cookie jar")

    def action(client, cass):
        client.request("GET", cass.url + "/cookies/set")
        return client.request("GET", cass.url + "/echo").json()["headers"].get("Cookie")

    recorded, replayed = record_and_replay(path, upstream, client, action)
    assert recorded == replayed == "session=abc"


def test_many_requests_on_one_session(path, upstream, client):
    def action(client, cass):
        return [client.request("GET", cass.url + f"/echo?i={i}").json()["path"] for i in range(5)]

    recorded, replayed = record_and_replay(path, upstream, client, action)
    assert recorded == replayed == [f"/echo?i={i}" for i in range(5)]


def test_unrecorded_request_in_none_mode(path, upstream, client):
    client.open()
    try:
        with (
            pytest.raises(CannotOverwriteExistingCassetteException),
            vcr.use_cassette(path, base_url=upstream.url, record_mode="none") as cass,
        ):
            assert client.request("GET", cass.url + "/echo").status == ERROR_STATUS
    finally:
        client.close()
    assert upstream.hits == []


@pytest.mark.parametrize("signed", [False, True], ids=["unsigned", "signed"])
def test_boto3_with_endpoint_url(path, upstream, signed):
    boto3 = pytest.importorskip("boto3")
    from botocore import UNSIGNED
    from botocore.config import Config

    def list_buckets(cass):
        s3 = boto3.client(
            "s3",
            endpoint_url=cass.url,
            region_name="us-east-1",
            aws_access_key_id="testing",
            aws_secret_access_key="testing",
            config=Config(signature_version=None if signed else UNSIGNED, retries={"max_attempts": 1}),
        )
        return [bucket["Name"] for bucket in s3.list_buckets()["Buckets"]]

    results = []
    for record_mode in ("once", "none"):
        with vcr.use_cassette(path, base_url=upstream.url + "/s3", record_mode=record_mode) as cass:
            results.append(list_buckets(cass))
    assert results == [["recorded-bucket"], ["recorded-bucket"]]
    assert len(upstream.hits) == 1
