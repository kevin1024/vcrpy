# -*- coding: utf-8 -*-
'''Test using a proxy.'''

# External imports
import multiprocessing
import pytest

from six.moves import socketserver, SimpleHTTPServer
from six.moves.urllib.request import urlopen

# Internal imports
import vcr

# Conditional imports
requests = pytest.importorskip("requests")


class Proxy(SimpleHTTPServer.SimpleHTTPRequestHandler):
    '''
    Simple proxy server.

    (Inspired by: http://effbot.org/librarybook/simplehttpserver.htm).
    '''
    def do_GET(self):
        upstream_response = urlopen(self.path)
        self.send_response(upstream_response.status, upstream_response.msg)
        for header in upstream_response.headers.items():
            self.send_header(*header)
        self.end_headers()
        self.copyfile(upstream_response, self.wfile)


@pytest.yield_fixture(scope='session')
def proxy_server():
    httpd = socketserver.ThreadingTCPServer(('', 0), Proxy)
    proxy_process = multiprocessing.Process(
        target=httpd.serve_forever,
    )
    proxy_process.start()
    yield 'http://{0}:{1}'.format(*httpd.server_address)
    proxy_process.terminate()


def test_use_proxy(tmpdir, httpbin, proxy_server):
    '''Ensure that it works with a proxy.'''
    with vcr.use_cassette(str(tmpdir.join('proxy.yaml'))):
        requests.get(httpbin.url, proxies={'http': proxy_server})
        requests.get(httpbin.url, proxies={'http': proxy_server})
