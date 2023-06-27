"""Stubs for boto"""

from boto.https_connection import CertValidatingHTTPSConnection

from vcr.stubs import VCRHTTPSConnection


class VCRCertValidatingHTTPSConnection(VCRHTTPSConnection):
    _baseclass = CertValidatingHTTPSConnection
