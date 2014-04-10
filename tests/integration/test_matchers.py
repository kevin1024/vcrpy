import vcr
import pytest
from six.moves.urllib.request import urlopen


@pytest.fixture
def cassette(tmpdir):
    return str(tmpdir.join('test.yml'))


def test_method_matcher(cassette):
    # prepare cassete
    with vcr.use_cassette(cassette, match_on=['method']) as cass:
        urlopen('http://httpbin.org/')
        assert len(cass) == 1

    # play cassette with matching on method
    with vcr.use_cassette(cassette, match_on=['method']) as cass:
        urlopen('http://httpbin.org/get')
        assert cass.play_count == 1

    # should fail if method does not match
    with pytest.raises(vcr.errors.CannotOverwriteExistingCassetteException):
        with vcr.use_cassette(cassette, match_on=['method']) as cass:
            urlopen('http://httpbin.org/post', data=b'')  # is a POST request


def test_uri_matcher(cassette):
    # prepare cassete
    with vcr.use_cassette(cassette, match_on=['uri']) as cass:
        urlopen('http://httpbin.org/get?p1=q1&p2=q2')
        assert len(cass) == 1

    # play cassette with matching on uri
    with vcr.use_cassette(cassette, match_on=['uri']) as cass:
        urlopen('http://httpbin.org/get?p1=q1&p2=q2')
        assert cass.play_count == 1

    # should fail if uri does not match
    with pytest.raises(vcr.errors.CannotOverwriteExistingCassetteException):
        with vcr.use_cassette(cassette, match_on=['uri']) as cass:
            urlopen('http://httpbin.org/get?p2=q2&p1=q1')
