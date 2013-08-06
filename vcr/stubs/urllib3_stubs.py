'''Stubs for urllib3'''

from urllib3.connectionpool import VerifiedHTTPSConnection
from ..stubs import VCRHTTPSConnection


class VCRVerifiedHTTPSConnection(VCRHTTPSConnection, VerifiedHTTPSConnection):
    _baseclass = VerifiedHTTPSConnection
