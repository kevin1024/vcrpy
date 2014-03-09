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
    _HTTPSConnection = cpool.HTTPSConnection
except ImportError:  # pragma: no cover
    pass

try:
    # Try to save the original types for urllib3
    import urllib3
    _VerifiedHTTPSConnection = urllib3.connectionpool.VerifiedHTTPSConnection
except ImportError:  # pragma: no cover
    pass

try:
    # Try to save the original types for httplib2
    import httplib2
    _HTTPConnectionWithTimeout = httplib2.HTTPConnectionWithTimeout
    _HTTPSConnectionWithTimeout = httplib2.HTTPSConnectionWithTimeout
    _SCHEME_TO_CONNECTION = httplib2.SCHEME_TO_CONNECTION
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

    # patch httplib2
    try:
        import httplib2 as cpool
        from .stubs.httplib2_stubs import VCRHTTPConnectionWithTimeout
        from .stubs.httplib2_stubs import VCRHTTPSConnectionWithTimeout
        cpool.HTTPConnectionWithTimeout = VCRHTTPConnectionWithTimeout
        cpool.HTTPSConnectionWithTimeout = VCRHTTPSConnectionWithTimeout
        cpool.SCHEME_TO_CONNECTION = {
            'http': VCRHTTPConnectionWithTimeout,
            'https': VCRHTTPSConnectionWithTimeout
        }
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

    try:
        import httplib2 as cpool
        cpool.HTTPConnectionWithTimeout = _HTTPConnectionWithTimeout
        cpool.HTTPSConnectionWithTimeout = _HTTPSConnectionWithTimeout
        cpool.SCHEME_TO_CONNECTION = _SCHEME_TO_CONNECTION
    except ImportError:  # pragma: no cover
        pass
