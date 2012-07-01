import httplib
from contextlib import contextmanager
from .stubs import VCRHTTPConnection, VCRHTTPSConnection

_HTTPConnection = httplib.HTTPConnection
_HTTPSConnection = httplib.HTTPSConnection


def install(cassette_path):
    httplib.HTTPConnection = httplib.HTTP._connection_class = VCRHTTPConnection
    httplib.HTTPSConnection = httplib.HTTPS._connection_class = VCRHTTPSConnection
    httplib.HTTPConnection._vcr_cassette_path = cassette_path
    httplib.HTTPSConnection._vcr_cassette_path = cassette_path


def reset():
    httplib.HTTPConnection = httplib.HTTP._connection_class = _HTTPConnection
    httplib.HTTPSConnection = httplib.HTTPS._connection_class = \
            _HTTPSConnection


@contextmanager
def use_cassette(cassette_path):
    install(cassette_path)
    yield
    reset()
