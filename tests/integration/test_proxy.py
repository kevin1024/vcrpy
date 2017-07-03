# -*- coding: utf-8 -*-
'''Test using a proxy.'''

# External imports
import multiprocessing
import SocketServer
import SimpleHTTPServer
import pytest
requests = pytest.importorskip("requests")

from six.moves.urllib.request import urlopen

# Internal imports
import vcr


class Proxy(SimpleHTTPServer.SimpleHTTPRequestHandler):
    '''
    Simple proxy server.

    (from: http://effbot.org/librarybook/simplehttpserver.htm).
    '''
    def do_GET(self):
        self.copyfile(urlopen(self.path), self.wfile)


@pytest.yield_fixture(scope='session')
def proxy_server(httpbin):
    httpd = SocketServer.ForkingTCPServer(('', 0), Proxy)
    proxy_process = multiprocessing.Process(
        target=httpd.serve_forever,
    )
    proxy_process.start()
    yield 'http://{}:{}'.format(*httpd.server_address)
    proxy_process.terminate()


def test_use_proxy(tmpdir, httpbin, proxy_server):
    '''Ensure that it works with a proxy.'''
    with vcr.use_cassette(str(tmpdir.join('proxy.yaml'))) as cass:
        requests.get(httpbin.url, proxies={'http': proxy_server})
        requests.get(httpbin.url, proxies={'http': proxy_server})
