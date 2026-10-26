"""Regression test for reuse of a stale (server-closed) keep-alive connection.

vcrpy replaces urllib3's connection classes with socketless stubs and used to
force ``is_connection_dropped`` to always return ``False`` (a Windows playback
fix, #116). Applied to *real* recording connections, that disabled urllib3's
stale-connection check, so a keep-alive connection the server had already closed
would be reused -- raising ``ProtocolError('Connection aborted', ...)`` (an
intermittent BrokenPipe/RemoteDisconnected in CI).
"""

import socket
import threading
import time

import urllib3

import vcr


def _keepalive_then_close_server():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(5)
    port = sock.getsockname()[1]

    def serve():
        while True:
            try:
                conn, _ = sock.accept()
            except OSError:
                return
            try:
                conn.recv(65536)
                conn.sendall(
                    b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: keep-alive\r\n\r\nok",
                )
                # Hand the keep-alive connection back, then drop it server-side,
                # leaving the client with a pooled-but-dead socket.
                time.sleep(0.02)
                conn.close()
            except OSError:
                pass

    threading.Thread(target=serve, daemon=True).start()
    return sock, port


def test_stale_pooled_connection_is_not_reused(tmpdir):
    server_sock, port = _keepalive_then_close_server()
    try:
        pool = urllib3.HTTPConnectionPool("127.0.0.1", port, maxsize=1)
        with vcr.use_cassette(str(tmpdir.join("stale.yml"))):
            pool.urlopen("GET", "/", retries=False, preload_content=True)
            time.sleep(0.25)  # let the server's close land on the pooled socket
            response = pool.urlopen("GET", "/", retries=False, preload_content=True)
            assert response.status == 200
    finally:
        server_sock.close()
