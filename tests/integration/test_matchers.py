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

    with pytest.raises(vcr.errors.CannotOverwriteExistingCassetteException):
        with vcr.use_cassette(cassette, match_on=['method']) as cass:
            urlopen('http://httpbin.org/post', data='')
