import vcr
from six.moves.urllib.request import urlopen


def true_matcher(r1, r2):
    return True


def false_matcher(r1, r2):
    return False


def test_registered_true_matcher(tmpdir):
    my_vcr = vcr.VCR()
    my_vcr.register_matcher('true', true_matcher)
    testfile = str(tmpdir.join('test.yml'))
    with my_vcr.use_cassette(testfile, match_on=['true']):
        # These 2 different urls are stored as the same request
        urlopen('http://httpbin.org/')
        urlopen('https://httpbin.org/get')

    with my_vcr.use_cassette(testfile, match_on=['true']):
        # I can get the response twice even though I only asked for it once
        urlopen('http://httpbin.org/get')
        urlopen('https://httpbin.org/get')


def test_registered_false_matcher(tmpdir):
    my_vcr = vcr.VCR()
    my_vcr.register_matcher('false', false_matcher)
    testfile = str(tmpdir.join('test.yml'))
    with my_vcr.use_cassette(testfile, match_on=['false']) as cass:
        # These 2 different urls are stored as different requests
        urlopen('http://httpbin.org/')
        urlopen('https://httpbin.org/get')
        assert len(cass) == 2
