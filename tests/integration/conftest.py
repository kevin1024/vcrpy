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
