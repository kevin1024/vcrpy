'''Utilities for patching in cassettes'''
import types

import contextlib2
import mock

from .stubs import VCRHTTPConnection, VCRHTTPSConnection
from six.moves import http_client as httplib


# Save some of the original types for the purposes of unpatching
_HTTPConnection = httplib.HTTPConnection
_HTTPSConnection = httplib.HTTPSConnection


# Try to save the original types for requests
try:
    import requests.packages.urllib3.connectionpool as cpool
except ImportError:  # pragma: no cover
    pass
else:
    _VerifiedHTTPSConnection = cpool.VerifiedHTTPSConnection
    _cpoolHTTPConnection = cpool.HTTPConnection
    _cpoolHTTPSConnection = cpool.HTTPSConnection


# Try to save the original types for urllib3
try:
    import urllib3
except ImportError:  # pragma: no cover
    pass
else:
    _VerifiedHTTPSConnection = urllib3.connectionpool.VerifiedHTTPSConnection


# Try to save the original types for httplib2
try:
    import httplib2
except ImportError:  # pragma: no cover
    pass
else:
    _HTTPConnectionWithTimeout = httplib2.HTTPConnectionWithTimeout
    _HTTPSConnectionWithTimeout = httplib2.HTTPSConnectionWithTimeout
    _SCHEME_TO_CONNECTION = httplib2.SCHEME_TO_CONNECTION


# Try to save the original types for boto
try:
    import boto.https_connection
except ImportError:  # pragma: no cover
    pass
else:
    _CertValidatingHTTPSConnection = boto.https_connection.CertValidatingHTTPSConnection



def cassette_subclass(base_class, cassette):
    bases = (base_class,)
    if not issubclass(base_class, object): # Check for old style class
        bases += (object,)
    return type('{0}{1}'.format(base_class.__name__, cassette._path), bases, dict(cassette=cassette))


def build_patchers(cassette):
    """
    Build patches for all the HTTPConnections references we can find!
    This replaces the actual HTTPConnection with a VCRHTTPConnection
    object which knows how to save to / read from cassettes
    """
    _VCRHTTPConnection = cassette_subclass(VCRHTTPConnection, cassette)
    _VCRHTTPSConnection = cassette_subclass(VCRHTTPSConnection, cassette)


    yield mock.patch.object(httplib, 'HTTPConnection', _VCRHTTPConnection)
    yield mock.patch.object(httplib, 'HTTPSConnection', _VCRHTTPSConnection)

    # requests
    try:
        import requests.packages.urllib3.connectionpool as cpool
    except ImportError:  # pragma: no cover
        pass
    else:
        from .stubs.requests_stubs import VCRRequestsHTTPConnection, VCRRequestsHTTPSConnection
        # patch requests v1.x
        yield mock.patch.object(cpool, 'VerifiedHTTPSConnection', cassette_subclass(VCRRequestsHTTPSConnection, cassette))
        yield mock.patch.object(cpool, 'HTTPConnection', cassette_subclass(VCRRequestsHTTPConnection, cassette))
        yield mock.patch.object(cpool, 'HTTPConnection', _VCRHTTPConnection)
        # patch requests v2.x
        yield mock.patch.object(cpool.HTTPConnectionPool, 'ConnectionCls', cassette_subclass(VCRRequestsHTTPConnection, cassette))
        yield mock.patch.object(cpool.HTTPSConnectionPool, 'ConnectionCls', cassette_subclass(VCRRequestsHTTPSConnection, cassette))

    # patch urllib3
    try:
        import urllib3.connectionpool as cpool
    except ImportError:  # pragma: no cover
        pass
    else:
        from .stubs.urllib3_stubs import VCRVerifiedHTTPSConnection
        yield mock.patch.object(cpool, 'VerifiedHTTPSConnection', cassette_subclass(VCRVerifiedHTTPSConnection, cassette))
        yield mock.patch.object(cpool, 'HTTPConnection', _VCRHTTPConnection)

    # patch httplib2
    try:
        import httplib2 as cpool
    except ImportError:  # pragma: no cover
        pass
    else:
        from .stubs.httplib2_stubs import VCRHTTPConnectionWithTimeout
        from .stubs.httplib2_stubs import VCRHTTPSConnectionWithTimeout
        yield mock.patch.object(cpool, 'HTTPConnectionWithTimeout', cassette_subclass(VCRHTTPConnectionWithTimeout, cassette))
        yield mock.patch.object(cpool, 'HTTPSConnectionWithTimeout', cassette_subclass(VCRHTTPSConnectionWithTimeout, cassette))
        yield mock.patch.object(cpool, 'SCHEME_TO_CONNECTION', {'http': VCRHTTPConnectionWithTimeout, 'https': VCRHTTPSConnectionWithTimeout})

    # patch boto
    try:
        import boto.https_connection as cpool
    except ImportError:  # pragma: no cover
        pass
    else:
        from .stubs.boto_stubs import VCRCertValidatingHTTPSConnection
        yield mock.patch.object(cpool, 'CertValidatingHTTPSConnection', cassette_subclass(VCRCertValidatingHTTPSConnection, cassette))


def reset_patchers():
    yield mock.patch.object(httplib, 'HTTPConnection', _HTTPConnection)
    yield mock.patch.object(httplib, 'HTTPSConnection', _HTTPSConnection)
    try:
        import requests.packages.urllib3.connectionpool as cpool
    except ImportError:  # pragma: no cover
        pass
    else:
        # unpatch requests v1.x
        yield mock.patch.object(cpool, 'VerifiedHTTPSConnection', _VerifiedHTTPSConnection)
        yield mock.patch.object(cpool, 'HTTPConnection', _cpoolHTTPConnection)
        # unpatch requests v2.x
        yield mock.patch.object(cpool.HTTPConnectionPool, 'ConnectionCls', _cpoolHTTPConnection)
        yield mock.patch.object(cpool, 'HTTPSConnection', _cpoolHTTPSConnection)
        yield mock.patch.object(cpool.HTTPSConnectionPool, 'ConnectionCls', _cpoolHTTPSConnection)

    try:
        import urllib3.connectionpool as cpool
    except ImportError:  # pragma: no cover
        pass
    else:
        yield mock.patch.object(cpool, 'VerifiedHTTPSConnection', _VerifiedHTTPSConnection)
        yield mock.patch.object(cpool, 'HTTPConnection', _HTTPConnection)
        yield mock.patch.object(cpool, 'HTTPSConnection', _HTTPSConnection)
        yield mock.patch.object(cpool.HTTPConnectionPool, 'ConnectionCls', _HTTPConnection)
        yield mock.patch.object(cpool.HTTPSConnectionPool, 'ConnectionCls', _HTTPSConnection)

    try:
        import httplib2 as cpool
    except ImportError:  # pragma: no cover
        pass
    else:
        yield mock.patch.object(cpool, 'HTTPConnectionWithTimeout', _HTTPConnectionWithTimeout)
        yield mock.patch.object(cpool, 'HTTPSConnectionWithTimeout', _HTTPSConnectionWithTimeout)
        yield mock.patch.object(cpool, 'SCHEME_TO_CONNECTION', _SCHEME_TO_CONNECTION)

    try:
        import boto.https_connection as cpool
    except ImportError:  # pragma: no cover
        pass
    else:
        yield mock.patch.object(cpool, 'CertValidatingHTTPSConnection', _CertValidatingHTTPSConnection)

@contextlib2.contextmanager
def force_reset():
    with contextlib2.ExitStack() as exit_stack:
        for patcher in reset_patchers():
            exit_stack.enter_context(patcher)
        yield
