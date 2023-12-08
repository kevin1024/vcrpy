"""Test using a proxy."""

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


@pytest.fixture(scope="session")
def proxy_server():
    httpd = socketserver.ThreadingTCPServer(("", 0), Proxy)
    proxy_process = threading.Thread(target=httpd.serve_forever)
    proxy_process.start()
    yield "http://{}:{}".format(*httpd.server_address)
    httpd.shutdown()
    proxy_process.join()


def test_use_proxy(tmpdir, httpbin, proxy_server):
    """Ensure that it works with a proxy."""
    with vcr.use_cassette(str(tmpdir.join("proxy.yaml"))):
        response = requests.get(httpbin.url, proxies={"http": proxy_server})

    with vcr.use_cassette(str(tmpdir.join("proxy.yaml")), mode="once") as cassette:
        cassette_response = requests.get(httpbin.url, proxies={"http": proxy_server})

    for key in set(cassette_response.headers.keys()) & set(response.headers.keys()):
        assert cassette_response.headers[key] == response.headers[key]
    assert cassette_response.headers == response.headers
    assert cassette.play_count == 1
