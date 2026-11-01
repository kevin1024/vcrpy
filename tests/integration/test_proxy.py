"""Test using a proxy."""

import asyncio
import http.server
import select
import socket
import socketserver
import threading
from urllib.request import ProxyHandler, build_opener

import pytest
import pytest_httpbin.certs

import vcr

# Conditional imports
requests = pytest.importorskip("requests")

_proxy_opener = build_opener(ProxyHandler({}))


class Proxy(http.server.SimpleHTTPRequestHandler):
    """
    Simple proxy server.

    (Inspired by: http://effbot.org/librarybook/simplehttpserver.htm).
    """

    def do_GET(self):
        upstream_response = _proxy_opener.open(self.path)
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
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
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


def test_use_proxy_from_environment_records_origin_url(tmpdir, httpbin, proxy_server, monkeypatch):
    """Ensure cassettes recorded through env proxies can replay without that proxy."""
    monkeypatch.delenv("no_proxy", raising=False)
    monkeypatch.delenv("NO_PROXY", raising=False)
    monkeypatch.setenv("http_proxy", proxy_server)

    with vcr.use_cassette(str(tmpdir.join("proxy.yaml"))):
        response = requests.get(httpbin.url)

    monkeypatch.delenv("http_proxy")

    with vcr.use_cassette(str(tmpdir.join("proxy.yaml")), mode="none") as cassette:
        cassette_response = requests.get(httpbin.url)

    assert cassette_response.headers == response.headers
    assert cassette.play_count == 1
    assert cassette.requests[0].url == httpbin.url + "/"


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


class Socks5Proxy(socketserver.BaseRequestHandler):
    """A SOCKS5 proxy without authentication that only supports CONNECT."""

    connections = 0

    def handle(self):
        client = self.request
        client.recv(client.recv(2)[1])  # the authentication methods the client offers
        client.sendall(b"\x05\x00")  # no authentication
        _, _, _, address_type = client.recv(4)
        if address_type == 1:
            host = socket.inet_ntoa(client.recv(4))
        else:
            host = client.recv(client.recv(1)[0]).decode()
        port = int.from_bytes(client.recv(2), "big")
        type(self).connections += 1
        with socket.create_connection((host, port)) as upstream:
            client.sendall(b"\x05\x00\x00\x01" + socket.inet_aton("0.0.0.0") + b"\x00\x00")
            sockets = [client, upstream]
            while True:
                readable, _, _ = select.select(sockets, [], [])
                for sock in readable:
                    data = sock.recv(65536)
                    if not data:
                        return
                    (upstream if sock is client else client).sendall(data)


@pytest.fixture(scope="session")
def socks_proxy():
    pytest.importorskip("socks")
    with socketserver.ThreadingTCPServer(("127.0.0.1", 0), Socks5Proxy) as server:
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever)
        thread.start()
        yield f"socks5h://127.0.0.1:{server.server_address[1]}"
        server.shutdown()
        thread.join()


@pytest.mark.parametrize("scheme", ["http", "https"])
def test_use_socks_proxy(tmpdir, httpbin, httpbin_secure, socks_proxy, scheme):
    # Pools for SOCKS proxies use their own connection classes, which weren't
    # patched, so their requests skipped the cassette (#547, #548).
    url = (httpbin if scheme == "http" else httpbin_secure).url + "/get"
    proxies = {"http": socks_proxy, "https": socks_proxy}
    verify = pytest_httpbin.certs.where()
    path = str(tmpdir.join("socks.yaml"))

    with vcr.use_cassette(path), requests.Session() as session:
        recorded = session.get(url, proxies=proxies, verify=verify)
    assert recorded.status_code == 200

    connections = Socks5Proxy.connections
    with vcr.use_cassette(path, record_mode="none") as cassette, requests.Session() as session:
        played = session.get(url, proxies=proxies, verify=verify)
    assert cassette.play_count == 1
    assert played.content == recorded.content
    assert Socks5Proxy.connections == connections

    with requests.Session() as session:
        assert session.get(url, proxies=proxies, verify=verify).status_code == 200
    assert Socks5Proxy.connections == connections + 1
