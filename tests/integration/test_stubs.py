import vcr
import six.moves.http_client as httplib


def _headers_are_case_insensitive(host, port):
    conn = httplib.HTTPConnection(host, port)
    conn.request('GET', "/cookies/set?k1=v1")
    r1 = conn.getresponse()
    cookie_data1 = r1.getheader('set-cookie')
    conn = httplib.HTTPConnection(host, port)
    conn.request('GET', "/cookies/set?k1=v1")
    r2 = conn.getresponse()
    cookie_data2 = r2.getheader('Set-Cookie')
    return cookie_data1 == cookie_data2


def test_case_insensitivity(tmpdir, httpbin):
    testfile = str(tmpdir.join('case_insensitivity.yml'))
    # check if headers are case insensitive outside of vcrpy
    host, port = httpbin.host, httpbin.port
    outside = _headers_are_case_insensitive(host, port)
    with vcr.use_cassette(testfile):
        # check if headers are case insensitive inside of vcrpy
        inside = _headers_are_case_insensitive(host, port)
        # check if headers are case insensitive after vcrpy deserializes headers
        inside2 = _headers_are_case_insensitive(host, port)

    # behavior should be the same both inside and outside
    assert outside == inside == inside2


def _multiple_header_value(httpbin):
    conn = httplib.HTTPConnection(httpbin.host, httpbin.port)
    conn.request('GET', "/response-headers?foo=bar&foo=baz")
    r = conn.getresponse()
    return r.getheader('foo')


def test_multiple_headers(tmpdir, httpbin):
    testfile = str(tmpdir.join('multiple_headers.yaml'))
    outside = _multiple_header_value(httpbin)

    with vcr.use_cassette(testfile):
        inside = _multiple_header_value(httpbin)

    assert outside == inside
