'''Utilities for patching in cassettes'''
import itertools

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


class PatcherBuilder(object):

    def __init__(self, cassette):
        self._cassette = cassette

    def build_patchers(self):
        patcher_args = itertools.chain(self._httplib(), self._requests(), self._urllib3(),
                                       self._httplib2(), self._boto())
        for obj, patched_attribute, replacement_class in patcher_args:
            patcher = self._build_patcher(obj, patched_attribute, replacement_class)
            if patcher:
                yield patcher
                if hasattr(replacement_class, 'cassette'):
                    yield mock.patch.object(replacement_class, 'cassette', self._cassette)

    def _build_patcher(self, obj, patched_attribute, replacement_class):
        if not hasattr(obj, patched_attribute):
            return
        return mock.patch.object(obj, patched_attribute, replacement_class)

    def _httplib(self):
        yield httplib, 'HTTPConnection', VCRHTTPConnection
        yield httplib, 'HTTPSConnection', VCRHTTPSConnection

    def _requests(self):
        try:
            import requests.packages.urllib3.connectionpool as cpool
        except ImportError:  # pragma: no cover
            pass
        else:
            from .stubs.requests_stubs import VCRRequestsHTTPConnection, VCRRequestsHTTPSConnection

            yield cpool, 'VerifiedHTTPSConnection', VCRRequestsHTTPSConnection
            yield cpool, 'VerifiedHTTPSConnection', VCRRequestsHTTPSConnection
            yield cpool, 'HTTPConnection', VCRRequestsHTTPConnection
            yield cpool, 'HTTPConnection', VCRHTTPConnection
            yield cpool.HTTPConnectionPool, 'ConnectionCls', VCRRequestsHTTPConnection
            yield cpool.HTTPSConnectionPool, 'ConnectionCls', VCRRequestsHTTPSConnection

    def _urllib3(self):
        try:
            import urllib3.connectionpool as cpool
        except ImportError:  # pragma: no cover
            pass
        else:
            from .stubs.urllib3_stubs import VCRVerifiedHTTPSConnection

            yield cpool, 'VerifiedHTTPSConnection', VCRVerifiedHTTPSConnection
            yield cpool, 'HTTPConnection', VCRHTTPConnection

    def _httplib2(self):
        try:
            import httplib2 as cpool
        except ImportError:  # pragma: no cover
            pass
        else:
            from .stubs.httplib2_stubs import VCRHTTPConnectionWithTimeout
            from .stubs.httplib2_stubs import VCRHTTPSConnectionWithTimeout

            yield cpool, 'HTTPConnectionWithTimeout', VCRHTTPConnectionWithTimeout
            yield cpool, 'HTTPSConnectionWithTimeout', VCRHTTPSConnectionWithTimeout
            yield cpool, 'SCHEME_TO_CONNECTION', {'http': VCRHTTPConnectionWithTimeout,
                                                  'https': VCRHTTPSConnectionWithTimeout}

    def _boto(self):
        try:
            import boto.https_connection as cpool
        except ImportError:  # pragma: no cover
            pass
        else:
            from .stubs.boto_stubs import VCRCertValidatingHTTPSConnection
            yield cpool, 'CertValidatingHTTPSConnection', VCRCertValidatingHTTPSConnection


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
        if hasattr(cpool.HTTPConnectionPool, 'ConnectionCls'):
            yield mock.patch.object(cpool.HTTPConnectionPool, 'ConnectionCls',
                                    _cpoolHTTPConnection)
            yield mock.patch.object(cpool.HTTPSConnectionPool, 'ConnectionCls',
                                    _cpoolHTTPSConnection)

        if hasattr(cpool, 'HTTPSConnection'):
            yield mock.patch.object(cpool, 'HTTPSConnection', _cpoolHTTPSConnection)

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
        yield mock.patch.object(cpool, 'CertValidatingHTTPSConnection',
                                _CertValidatingHTTPSConnection)


@contextlib2.contextmanager
def force_reset():
    with contextlib2.ExitStack() as exit_stack:
        for patcher in reset_patchers():
            exit_stack.enter_context(patcher)
        yield
