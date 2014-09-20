'''Utilities for patching in cassettes'''
import functools
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


class CassettePatcherBuilder(object):

    def _build_patchers_from_mock_triples_decorator(function):
        @functools.wraps(function)
        def wrapped(self, *args, **kwargs):
            return self._build_patchers_from_mock_triples(function(self, *args, **kwargs))
        return wrapped

    def __init__(self, cassette):
        self._cassette = cassette
        self._class_to_cassette_subclass = {}

    def build(self):
        return itertools.chain(self._httplib(), self._requests(),
                               self._urllib3(), self._httplib2(),
                               self._boto())

    def _build_patchers_from_mock_triples(self, mock_triples):
        for args in mock_triples:
            patcher = self._build_patcher(*args)
            if patcher:
                yield patcher

    def _build_patcher(self, obj, patched_attribute, replacement_class):
        if not hasattr(obj, patched_attribute):
            return

        return mock.patch.object(obj, patched_attribute,
                                 self._recursively_apply_get_cassette_subclass(
                                     replacement_class))

    def _recursively_apply_get_cassette_subclass(self, replacement_dict_or_obj):
        if isinstance(replacement_dict_or_obj, dict):
            for key, replacement_obj  in replacement_dict_or_obj:
                replacement_obj = self._recursively_apply_get_cassette_subclass(
                    replacement_obj)
                replacement_dict_or_obj[key] = replacement_obj
            return replacement_dict_or_obj
        if hasattr(replacement_dict_or_obj, 'cassette'):
            replacement_dict_or_obj =  self._get_cassette_subclass(
                replacement_dict_or_obj)
        return replacement_dict_or_obj

    def _get_cassette_subclass(self, klass):
        if klass.cassette is not None:
            return klass
        if klass not in self._class_to_cassette_subclass:
            subclass = self._build_cassette_subclass(klass)
            self._class_to_cassette_subclass[klass] = subclass
        return self._class_to_cassette_subclass[klass]

    def _build_cassette_subclass(self, base_class):
        bases = (base_class,)
        if not issubclass(base_class, object): # Check for old style class
            bases += (object,)
        return type('{0}{1}'.format(base_class.__name__, self._cassette._path),
                    bases, dict(cassette=self._cassette))

    @_build_patchers_from_mock_triples_decorator
    def _httplib(self):
        yield httplib, 'HTTPConnection', VCRHTTPConnection
        yield httplib, 'HTTPSConnection', VCRHTTPSConnection

    def _requests(self):
        try:
            import requests.packages.urllib3.connectionpool as cpool
        except ImportError:  # pragma: no cover
            return
        from .stubs.requests_stubs import VCRRequestsHTTPConnection, VCRRequestsHTTPSConnection
        mock_triples = (
            (cpool, 'VerifiedHTTPSConnection', VCRRequestsHTTPSConnection),
            (cpool, 'VerifiedHTTPSConnection', VCRRequestsHTTPSConnection),
            (cpool, 'HTTPConnection', VCRRequestsHTTPConnection),
            (cpool, 'HTTPSConnection', VCRRequestsHTTPSConnection),
            (cpool.HTTPConnectionPool, 'ConnectionCls', VCRRequestsHTTPConnection),
            (cpool.HTTPSConnectionPool, 'ConnectionCls', VCRRequestsHTTPSConnection),
            # These handle making sure that sessions only use the
            # connections of the appropriate type.
        )
        mock_triples += ((cpool.HTTPConnectionPool, '_get_conn',
                          self._patched_get_conn(cpool.HTTPConnectionPool,
                                                 lambda : cpool.HTTPConnection)),
                         (cpool.HTTPSConnectionPool, '_get_conn',
                          self._patched_get_conn(cpool.HTTPSConnectionPool,
                                                 lambda : cpool.HTTPSConnection)))
        return self._build_patchers_from_mock_triples(mock_triples)

    def _patched_get_conn(self, connection_pool_class, connection_class_getter):
        get_conn = connection_pool_class._get_conn
        @functools.wraps(get_conn)
        def patched_get_conn(pool, timeout=None):
            connection = get_conn(pool, timeout)
            connection_class = pool.ConnectionCls if hasattr(pool, 'ConnectionCls') \
                               else connection_class_getter()
            while not isinstance(connection, connection_class):
                connection = get_conn(pool, timeout)
            return connection
        return patched_get_conn

    @_build_patchers_from_mock_triples_decorator
    def _urllib3(self):
        try:
            import urllib3.connectionpool as cpool
        except ImportError:  # pragma: no cover
            pass
        else:
            from .stubs.urllib3_stubs import VCRVerifiedHTTPSConnection

            yield cpool, 'VerifiedHTTPSConnection', VCRVerifiedHTTPSConnection
            yield cpool, 'HTTPConnection', VCRHTTPConnection

    @_build_patchers_from_mock_triples_decorator
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

    @_build_patchers_from_mock_triples_decorator
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
