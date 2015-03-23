'''Integration tests with urllib3'''

# coding=utf-8

import pytest
import vcr
from assertions import assert_cassette_empty, assert_is_json
certifi = pytest.importorskip("certifi")
urllib3 = pytest.importorskip("urllib3")


@pytest.fixture(params=["https", "http"])
def scheme(request):
    """
    Fixture that returns both http and https
    """
    return request.param


@pytest.fixture(scope='module')
def verify_pool_mgr():
    return urllib3.PoolManager(
        cert_reqs='CERT_REQUIRED', # Force certificate check.
        ca_certs=certifi.where()
    )


@pytest.fixture(scope='module')
def pool_mgr():
    return urllib3.PoolManager()


def test_status_code(scheme, tmpdir, verify_pool_mgr):
    '''Ensure that we can read the status code'''
    url = scheme + '://httpbin.org/'
    with vcr.use_cassette(str(tmpdir.join('atts.yaml'))):
        status_code = verify_pool_mgr.request('GET', url).status

    with vcr.use_cassette(str(tmpdir.join('atts.yaml'))):
        assert status_code == verify_pool_mgr.request('GET', url).status


def test_headers(scheme, tmpdir, verify_pool_mgr):
    '''Ensure that we can read the headers back'''
    url = scheme + '://httpbin.org/'
    with vcr.use_cassette(str(tmpdir.join('headers.yaml'))):
        headers = verify_pool_mgr.request('GET', url).headers

    with vcr.use_cassette(str(tmpdir.join('headers.yaml'))):
        assert headers == verify_pool_mgr.request('GET', url).headers


def test_body(tmpdir, scheme, verify_pool_mgr):
    '''Ensure the responses are all identical enough'''
    url = scheme + '://httpbin.org/bytes/1024'
    with vcr.use_cassette(str(tmpdir.join('body.yaml'))):
        content = verify_pool_mgr.request('GET', url).data

    with vcr.use_cassette(str(tmpdir.join('body.yaml'))):
        assert content == verify_pool_mgr.request('GET', url).data


def test_auth(tmpdir, scheme, verify_pool_mgr):
    '''Ensure that we can handle basic auth'''
    auth = ('user', 'passwd')
    headers = urllib3.util.make_headers(basic_auth='{0}:{1}'.format(*auth))
    url = scheme + '://httpbin.org/basic-auth/user/passwd'
    with vcr.use_cassette(str(tmpdir.join('auth.yaml'))):
        one = verify_pool_mgr.request('GET', url, headers=headers)

    with vcr.use_cassette(str(tmpdir.join('auth.yaml'))):
        two = verify_pool_mgr.request('GET', url, headers=headers)
        assert one.data == two.data
        assert one.status == two.status


def test_auth_failed(tmpdir, scheme, verify_pool_mgr):
    '''Ensure that we can save failed auth statuses'''
    auth = ('user', 'wrongwrongwrong')
    headers = urllib3.util.make_headers(basic_auth='{0}:{1}'.format(*auth))
    url = scheme + '://httpbin.org/basic-auth/user/passwd'
    with vcr.use_cassette(str(tmpdir.join('auth-failed.yaml'))) as cass:
        # Ensure that this is empty to begin with
        assert_cassette_empty(cass)
        one = verify_pool_mgr.request('GET', url, headers=headers)
        two = verify_pool_mgr.request('GET', url, headers=headers)
        assert one.data == two.data
        assert one.status == two.status == 401


def test_post(tmpdir, scheme, verify_pool_mgr):
    '''Ensure that we can post and cache the results'''
    data = {'key1': 'value1', 'key2': 'value2'}
    url = scheme + '://httpbin.org/post'
    with vcr.use_cassette(str(tmpdir.join('verify_pool_mgr.yaml'))):
        req1 = verify_pool_mgr.request('POST', url, data).data

    with vcr.use_cassette(str(tmpdir.join('verify_pool_mgr.yaml'))):
        req2 = verify_pool_mgr.request('POST', url, data).data

    assert req1 == req2


def test_redirects(tmpdir, scheme, verify_pool_mgr):
    '''Ensure that we can handle redirects'''
    url = scheme + '://httpbin.org/redirect-to?url=bytes/1024'
    with vcr.use_cassette(str(tmpdir.join('verify_pool_mgr.yaml'))):
        content = verify_pool_mgr.request('GET', url).data

    with vcr.use_cassette(str(tmpdir.join('verify_pool_mgr.yaml'))) as cass:
        assert content == verify_pool_mgr.request('GET', url).data
        # Ensure that we've now cached *two* responses. One for the redirect
        # and one for the final fetch
        assert len(cass) == 2
        assert cass.play_count == 2


def test_cross_scheme(tmpdir, scheme, verify_pool_mgr):
    '''Ensure that requests between schemes are treated separately'''
    # First fetch a url under http, and then again under https and then
    # ensure that we haven't served anything out of cache, and we have two
    # requests / response pairs in the cassette
    with vcr.use_cassette(str(tmpdir.join('cross_scheme.yaml'))) as cass:
        verify_pool_mgr.request('GET', 'https://httpbin.org/')
        verify_pool_mgr.request('GET', 'http://httpbin.org/')
        assert cass.play_count == 0
        assert len(cass) == 2


def test_gzip(tmpdir, scheme, verify_pool_mgr):
    '''
    Ensure that requests (actually urllib3) is able to automatically decompress
    the response body
    '''
    url = scheme + '://httpbin.org/gzip'
    response = verify_pool_mgr.request('GET', url)

    with vcr.use_cassette(str(tmpdir.join('gzip.yaml'))):
        response = verify_pool_mgr.request('GET', url)
        assert_is_json(response.data)

    with vcr.use_cassette(str(tmpdir.join('gzip.yaml'))):
        assert_is_json(response.data)


def test_https_with_cert_validation_disabled(tmpdir, pool_mgr):
    with vcr.use_cassette(str(tmpdir.join('cert_validation_disabled.yaml'))):
        pool_mgr.request('GET', 'https://httpbin.org')
