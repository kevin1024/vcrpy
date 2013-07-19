import httplib
from contextlib import contextmanager
from .stubs import VCRHTTPConnection, VCRHTTPSConnection


_HTTPConnection = httplib.HTTPConnection
_HTTPSConnection = httplib.HTTPSConnection

try:
    import requests.packages.urllib3.connectionpool
    _VerifiedHTTPSConnection = requests.packages.urllib3.connectionpool.VerifiedHTTPSConnection
    _HTTPConnection = requests.packages.urllib3.connectionpool.HTTPConnection
except ImportError:
    pass

try:
    import urllib3
    _VerifiedHTTPSConnection = urllib3.connectionpool.VerifiedHTTPSConnection 
except ImportError:
    pass


def install(cassette_path):
    httplib.HTTPConnection = httplib.HTTP._connection_class = VCRHTTPConnection
    httplib.HTTPSConnection = httplib.HTTPS._connection_class = VCRHTTPSConnection
    httplib.HTTPConnection._vcr_cassette_path = cassette_path
    httplib.HTTPSConnection._vcr_cassette_path = cassette_path

    #patch requests
    try:
        import requests.packages.urllib3.connectionpool
        from .requests_stubs import VCRVerifiedHTTPSConnection
        requests.packages.urllib3.connectionpool.VerifiedHTTPSConnection = VCRVerifiedHTTPSConnection
        requests.packages.urllib3.connectionpool.VerifiedHTTPSConnection._vcr_cassette_path = cassette_path
        requests.packages.urllib3.connectionpool.HTTPConnection = VCRHTTPConnection
        requests.packages.urllib3.connectionpool.HTTPConnection._vcr_cassette_path = cassette_path
    except ImportError:
        pass

    #patch urllib3
    try:
        import urllib3.connectionpool
        from .urllib3_stubs import VCRVerifiedHTTPSConnection
        urllib3.connectionpool.VerifiedHTTPSConnection = VCRVerifiedHTTPSConnection
        urllib3.connectionpool.VerifiedHTTPSConnection._vcr_cassette_path = cassette_path
        urllib3.connectionpool.HTTPConnection = VCRHTTPConnection
        urllib3.connectionpool.HTTPConnection._vcr_cassette_path = cassette_path
    except ImportError:
        pass


def reset():
    httplib.HTTPConnection = httplib.HTTP._connection_class = _HTTPConnection
    httplib.HTTPSConnection = httplib.HTTPS._connection_class = \
            _HTTPSConnection
    try:
        import requests.packages.urllib3.connectionpool
        requests.packages.urllib3.connectionpool.VerifiedHTTPSConnection = _VerifiedHTTPSConnection
        requests.packages.urllib3.connectionpool.HTTPConnection = _HTTPConnection
    except ImportError:
        pass

    try:
        import urllib3.connectionpool
        urllib3.connectionpool.VerifiedHTTPSConnection = _VerifiedHTTPSConnection
        urllib3.connectionpool.HTTPConnection = _HTTPConnection
    except ImportError:
        pass


@contextmanager
def use_cassette(cassette_path):
    install(cassette_path)
    yield
    reset()
