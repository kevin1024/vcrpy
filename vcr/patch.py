'''Utilities for patching in cassettes'''

import httplib
from .stubs import VCRHTTPConnection, VCRHTTPSConnection


# Save some of the original types for the purposes of unpatching
_HTTPConnection = httplib.HTTPConnection
_HTTPSConnection = httplib.HTTPSConnection

try:
    # Try to save the original types for requests
    import requests.packages.urllib3.connectionpool as cpool
    _VerifiedHTTPSConnection = cpool.VerifiedHTTPSConnection
    _HTTPConnection = cpool.HTTPConnection
except ImportError:  # pragma: no cover
    pass

try:
    # Try to save the original types for urllib3
    import urllib3
    _VerifiedHTTPSConnection = urllib3.connectionpool.VerifiedHTTPSConnection
except ImportError:  # pragma: no cover
    pass


def install(cassette):
    """
    Patch all the HTTPConnections references we can find!
    This replaces the actual HTTPConnection with a VCRHTTPConnection
    object which knows how to save to / read from cassettes
    """
    httplib.HTTPConnection = httplib.HTTP._connection_class = VCRHTTPConnection
    httplib.HTTPSConnection = httplib.HTTPS._connection_class = (
        VCRHTTPSConnection)
    httplib.HTTPConnection.cassette = cassette
    httplib.HTTPSConnection.cassette = cassette

    # patch requests v1.x
    try:
        import requests.packages.urllib3.connectionpool as cpool
        from .stubs.requests_stubs import VCRVerifiedHTTPSConnection
        cpool.VerifiedHTTPSConnection = VCRVerifiedHTTPSConnection
        cpool.VerifiedHTTPSConnection.cassette = cassette
        cpool.HTTPConnection = VCRHTTPConnection
        cpool.HTTPConnection.cassette = cassette
    # patch requests v2.x
        cpool.HTTPConnectionPool.ConnectionCls = VCRHTTPConnection
        cpool.HTTPConnectionPool.cassette = cassette
        cpool.HTTPSConnectionPool.ConnectionCls = VCRHTTPSConnection
        cpool.HTTPSConnectionPool.cassette = cassette
    except ImportError:  # pragma: no cover
        pass

    # patch urllib3
    try:
        import urllib3.connectionpool as cpool
        from .stubs.urllib3_stubs import VCRVerifiedHTTPSConnection
        cpool.VerifiedHTTPSConnection = VCRVerifiedHTTPSConnection
        cpool.VerifiedHTTPSConnection.cassette = cassette
        cpool.HTTPConnection = VCRHTTPConnection
        cpool.HTTPConnection.cassette = cassette
    except ImportError:  # pragma: no cover
        pass


def reset():
    '''Undo all the patching'''
    httplib.HTTPConnection = httplib.HTTP._connection_class = _HTTPConnection
    httplib.HTTPSConnection = httplib.HTTPS._connection_class = \
        _HTTPSConnection
    try:
        import requests.packages.urllib3.connectionpool as cpool
        cpool.VerifiedHTTPSConnection = _VerifiedHTTPSConnection
        cpool.HTTPConnection = _HTTPConnection
        cpool.HTTPConnectionPool.ConnectionCls = _HTTPConnection
        cpool.HTTPSConnectionPool.ConnectionCls = _HTTPSConnection
    except ImportError:  # pragma: no cover
        pass

    try:
        import urllib3.connectionpool as cpool
        cpool.VerifiedHTTPSConnection = _VerifiedHTTPSConnection
        cpool.HTTPConnection = _HTTPConnection
        cpool.HTTPConnectionPool.ConnectionCls = _HTTPConnection
        cpool.HTTPSConnectionPool.ConnectionCls = _HTTPSConnection
    except ImportError:  # pragma: no cover
        pass
