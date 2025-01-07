"""Test using a proxy."""

import asyncio
import http.server
import socketserver
import threading
from urllib.request import urlopen

import pytest

import vcr

# Conditional imports
requests = pytest.importorskip("requests")


class Proxy(http.server.SimpleHTTPRequestHandler):
    """
    Simple proxy server.

    (Inspired by: http://effbot.org/librarybook/simplehttpserver.htm).
    """

    def do_GET(self):
        upstream_response = urlopen(self.path)
        try:
            status = upstream_response.status
            headers = upstream_response.headers.items()
        except AttributeError:
            # In Python 2 the response is an addinfourl instance.
            status = upstream_response.code
            headers = upstream_response.info().items()
        self.log_request(status)
        self.send_response_only(status, upstream_response.msg)
        for header in headers:
            self.send_header(*header)
        self.end_headers()
        self.copyfile(upstream_response, self.wfile)

    def do_CONNECT(self):
        host, port = self.path.split(":")

        asyncio.run(self._tunnel(host, port, self.connection))

    async def _tunnel(self, host, port, client_sock):
        target_r, target_w = await asyncio.open_connection(host=host, port=port)

        self.send_response(http.HTTPStatus.OK)
        self.end_headers()

        source_r, source_w = await asyncio.open_connection(sock=client_sock)

        async def channel(reader, writer):
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                writer.write(data)
                await writer.drain()

            writer.close()
            await writer.wait_closed()

        await asyncio.gather(
            channel(target_r, source_w),
            channel(source_r, target_w),
        )


@pytest.fixture(scope="session")
def proxy_server():
    with socketserver.ThreadingTCPServer(("", 0), Proxy) as httpd:
        proxy_process = threading.Thread(target=httpd.serve_forever)
        proxy_process.start()
        yield "http://{}:{}".format(*httpd.server_address)
        httpd.shutdown()
        proxy_process.join()


def test_use_proxy(tmpdir, httpbin, proxy_server):
    """Ensure that it works with a proxy."""
    with vcr.use_cassette(str(tmpdir.join("proxy.yaml"))):
        response = requests.get(httpbin.url, proxies={"http": proxy_server})

    with vcr.use_cassette(str(tmpdir.join("proxy.yaml")), mode="none") as cassette:
        cassette_response = requests.get(httpbin.url, proxies={"http": proxy_server})

    assert cassette_response.headers == response.headers
    assert cassette.play_count == 1


def test_use_https_proxy(tmpdir, httpbin_secure, proxy_server):
    """Ensure that it works with an HTTPS proxy."""
    with vcr.use_cassette(str(tmpdir.join("proxy.yaml"))):
        response = requests.get(httpbin_secure.url, proxies={"https": proxy_server})

    with vcr.use_cassette(str(tmpdir.join("proxy.yaml")), mode="none") as cassette:
        cassette_response = requests.get(
            httpbin_secure.url,
            proxies={"https": proxy_server},
        )

    assert cassette_response.headers == response.headers
    assert cassette.play_count == 1

    # The cassette URL points to httpbin, not the proxy
    assert cassette.requests[0].url == httpbin_secure.url + "/"
