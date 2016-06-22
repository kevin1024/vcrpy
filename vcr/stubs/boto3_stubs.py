'''Stubs for boto3'''

from botocore.vendored.requests.packages.urllib3.connectionpool import HTTPConnection, VerifiedHTTPSConnection
from ..stubs import VCRHTTPConnection, VCRHTTPSConnection

# urllib3 defines its own HTTPConnection classes, which boto3 goes ahead and assumes
# you're using.  It includes some polyfills for newer features missing in older pythons.


class VCRRequestsHTTPConnection(VCRHTTPConnection, HTTPConnection):
    _baseclass = HTTPConnection


class VCRRequestsHTTPSConnection(VCRHTTPSConnection, VerifiedHTTPSConnection):
    _baseclass = VerifiedHTTPSConnection
