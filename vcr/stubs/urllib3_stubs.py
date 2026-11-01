"""Stubs for urllib3"""

from importlib.util import find_spec

from urllib3 import HTTPHeaderDict
from urllib3.connection import HTTPConnection, VerifiedHTTPSConnection

from ..stubs import VCRHTTPConnection, VCRHTTPSConnection

# urllib3 defines its own HTTPConnection classes. It includes some polyfills
# for newer features missing in older pythons.


class _VCRRequestsConnectionMixin:
    def getresponse(self, *args, **kwargs):
        response = super().getresponse(*args, **kwargs)
        response.headers = HTTPHeaderDict(response.getheaders())
        return response


class VCRRequestsHTTPConnection(_VCRRequestsConnectionMixin, VCRHTTPConnection, HTTPConnection):
    _baseclass = HTTPConnection
    is_multiplexed = False


class VCRRequestsHTTPSConnection(_VCRRequestsConnectionMixin, VCRHTTPSConnection, VerifiedHTTPSConnection):
    _baseclass = VerifiedHTTPSConnection
    is_multiplexed = False


# urllib3's SOCKS proxy support needs PySocks, and warns when it's imported without it.
if find_spec("socks"):
    try:
        from urllib3.contrib.socks import SOCKSConnection, SOCKSHTTPSConnection
    except ImportError:  # pragma: no cover
        pass
    else:

        class VCRRequestsSOCKSConnection(_VCRRequestsConnectionMixin, VCRHTTPConnection, SOCKSConnection):
            _baseclass = SOCKSConnection
            is_multiplexed = False

        class VCRRequestsSOCKSHTTPSConnection(
            _VCRRequestsConnectionMixin,
            VCRHTTPSConnection,
            SOCKSHTTPSConnection,
        ):
            _baseclass = SOCKSHTTPSConnection
            is_multiplexed = False
