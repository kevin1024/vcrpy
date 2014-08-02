import vcr
import six.moves.http_client as httplib

def _headers_are_case_insensitive():
    conn = httplib.HTTPConnection('httpbin.org')
    conn.request('GET', "/cookies/set?k1=v1")
    r1 = conn.getresponse()
    cookie_data1 = r1.getheader('set-cookie')
    conn = httplib.HTTPConnection('httpbin.org')
    conn.request('GET', "/cookies/set?k1=v1")
    r2 = conn.getresponse()
    cookie_data2 = r2.getheader('Set-Cookie')
    return cookie_data1 == cookie_data2

def test_case_insensitivity(tmpdir):
    testfile = str(tmpdir.join('case_insensitivity.yml'))
    # check if headers are case insensitive outside of vcrpy
    outside = _headers_are_case_insensitive()
    with vcr.use_cassette(testfile):
        # check if headers are case insensitive inside of vcrpy
        inside = _headers_are_case_insensitive()
        # check if headers are case insensitive after vcrpy deserializes headers
        inside2 = _headers_are_case_insensitive()

    # behavior should be the same both inside and outside
    assert outside == inside == inside2
