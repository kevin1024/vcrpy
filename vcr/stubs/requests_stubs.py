'''Stubs for requests'''

from requests.packages.urllib3.connectionpool import VerifiedHTTPSConnection
from ..stubs import VCRHTTPSConnection


class VCRVerifiedHTTPSConnection(VCRHTTPSConnection, VerifiedHTTPSConnection):
    _baseclass = VerifiedHTTPSConnection
