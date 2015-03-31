import base64
import pytest
from six.moves.urllib.request import urlopen, Request
from six.moves.urllib.parse import urlencode
from six.moves.urllib.error import HTTPError
import vcr


def _request_with_auth(url, username, password):
    request = Request(url)
    base64string = base64.b64encode(
        username.encode('ascii') + b':' + password.encode('ascii')
    )
    request.add_header(b"Authorization", b"Basic " + base64string)
    return urlopen(request)


def _find_header(cassette, header):
    for request in cassette.requests:
        for k in request.headers:
            if header.lower() == k.lower():
                return True
    return False


def test_filter_basic_auth(tmpdir):
    url = 'http://httpbin.org/basic-auth/user/passwd'
    cass_file = str(tmpdir.join('basic_auth_filter.yaml'))
    my_vcr = vcr.VCR(match_on=['uri', 'method', 'headers'])
    # 2 requests, one with auth failure and one with auth success
    with my_vcr.use_cassette(cass_file, filter_headers=['authorization']):
        with pytest.raises(HTTPError):
            resp = _request_with_auth(url, 'user', 'wrongpasswd')
            assert resp.getcode() == 401
        resp = _request_with_auth(url, 'user', 'passwd')
        assert resp.getcode() == 200
    # make same 2 requests, this time both served from cassette.
    with my_vcr.use_cassette(cass_file, filter_headers=['authorization']) as cass:
        with pytest.raises(HTTPError):
            resp = _request_with_auth(url, 'user', 'wrongpasswd')
            assert resp.getcode() == 401
        resp = _request_with_auth(url, 'user', 'passwd')
        assert resp.getcode() == 200
        # authorization header should not have been recorded
        assert not _find_header(cass, 'authorization')
        assert len(cass) == 2


def test_filter_querystring(tmpdir):
    url = 'http://httpbin.org/?foo=bar'
    cass_file = str(tmpdir.join('filter_qs.yaml'))
    with vcr.use_cassette(cass_file, filter_query_parameters=['foo']):
        urlopen(url)
    with vcr.use_cassette(cass_file, filter_query_parameters=['foo']) as cass:
        urlopen(url)
        assert 'foo' not in cass.requests[0].url


def test_filter_post_data(tmpdir):
    url = 'http://httpbin.org/post'
    data = urlencode({'id': 'secret', 'foo': 'bar'}).encode('utf-8')
    cass_file = str(tmpdir.join('filter_pd.yaml'))
    with vcr.use_cassette(cass_file, filter_post_data_parameters=['id']):
        urlopen(url, data)
    with vcr.use_cassette(cass_file, filter_post_data_parameters=['id']) as cass:
        assert b'id=secret' not in cass.requests[0].body


def test_filter_callback(tmpdir):
    url = 'http://httpbin.org/get'
    cass_file = str(tmpdir.join('basic_auth_filter.yaml'))
    def before_record_cb(request):
        if request.path != '/get':
            return request
    # Test the legacy keyword.
    my_vcr = vcr.VCR(before_record=before_record_cb)
    with my_vcr.use_cassette(cass_file, filter_headers=['authorization']) as cass:
        urlopen(url)
        assert len(cass) == 0

    my_vcr = vcr.VCR(before_record_request=before_record_cb)
    with my_vcr.use_cassette(cass_file, filter_headers=['authorization']) as cass:
        urlopen(url)
        assert len(cass) == 0
