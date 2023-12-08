import os
import ssl

import pytest


@pytest.fixture
def httpbin_ssl_context():
    ssl_ca_location = os.environ["REQUESTS_CA_BUNDLE"]
    ssl_cert_location = os.environ["REQUESTS_CA_BUNDLE"].replace("cacert.pem", "cert.pem")
    ssl_key_location = os.environ["REQUESTS_CA_BUNDLE"].replace("cacert.pem", "key.pem")

    ssl_context = ssl.create_default_context(cafile=ssl_ca_location)
    ssl_context.load_cert_chain(ssl_cert_location, ssl_key_location)

    return ssl_context
