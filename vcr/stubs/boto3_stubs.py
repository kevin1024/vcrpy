"""Stubs for boto3"""

try:
    # boto using awsrequest
    from botocore.awsrequest import AWSHTTPConnection as HTTPConnection
    from botocore.awsrequest import AWSHTTPSConnection as VerifiedHTTPSConnection

except ImportError:  # pragma: nocover
    # boto using vendored requests
    # urllib3 defines its own HTTPConnection classes, which boto3 goes ahead and assumes
    # you're using.  It includes some polyfills for newer features missing in older pythons.
    try:
        from urllib3.connectionpool import HTTPConnection, VerifiedHTTPSConnection
    except ImportError:  # pragma: nocover
        from requests.packages.urllib3.connectionpool import HTTPConnection, VerifiedHTTPSConnection

from ..stubs import VCRHTTPConnection, VCRHTTPSConnection


class VCRRequestsHTTPConnection(VCRHTTPConnection, HTTPConnection):
    _baseclass = HTTPConnection


class VCRRequestsHTTPSConnection(VCRHTTPSConnection, VerifiedHTTPSConnection):
    _baseclass = VerifiedHTTPSConnection
