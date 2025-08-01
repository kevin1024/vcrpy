"""Stubs for docker"""

from docker.transport.unixconn import UnixHTTPConnection

from ..stubs import VCRHTTPConnection

# docker defines its own UnixHTTPConnection classes. It includes some polyfills
# for newer features missing in older pythons.


class VCRRequestsUnixHTTPConnection(VCRHTTPConnection, UnixHTTPConnection):
    _baseclass = UnixHTTPConnection
