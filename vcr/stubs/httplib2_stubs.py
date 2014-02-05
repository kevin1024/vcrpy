'''Stubs for urllib3'''

from httplib2 import HTTPConnectionWithTimeout, HTTPSConnectionWithTimeout
from ..stubs import VCRHTTPConnection, VCRHTTPSConnection


class VCRHTTPConnectionWithTimeout(VCRHTTPConnection,
                                   HTTPConnectionWithTimeout):
    _baseclass = HTTPConnectionWithTimeout


class VCRHTTPSConnectionWithTimeout(VCRHTTPSConnection,
                                    HTTPSConnectionWithTimeout):
    _baseclass = HTTPSConnectionWithTimeout
