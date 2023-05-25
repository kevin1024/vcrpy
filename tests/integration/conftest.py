import os
import ssl

import pytest


@pytest.fixture(params=["https", "http"])
def scheme(request):
    """Fixture that returns both http and https."""
    return request.param


@pytest.fixture
def mockbin(scheme):
    return scheme + "://mockbin.org"


@pytest.fixture
def mockbin_request_url(mockbin):
    return mockbin + "/request"


@pytest.fixture
def httpbin_ssl_context():
    ssl_ca_location = os.environ["REQUESTS_CA_BUNDLE"]
    ssl_cert_location = os.environ["REQUESTS_CA_BUNDLE"].replace("cacert.pem", "cert.pem")
    ssl_key_location = os.environ["REQUESTS_CA_BUNDLE"].replace("cacert.pem", "key.pem")

    ssl_context = ssl.create_default_context(cafile=ssl_ca_location)
    ssl_context.load_cert_chain(ssl_cert_location, ssl_key_location)

    return ssl_context
