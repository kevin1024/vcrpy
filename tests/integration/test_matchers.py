import vcr
import pytest
from six.moves.urllib.request import urlopen


DEFAULT_URI = 'http://httpbin.org/get?p1=q1&p2=q2'  # base uri for testing


@pytest.fixture
def cassette(tmpdir):
    """
    Helper fixture used to prepare the cassete
    returns path to the recorded cassette
    """
    cassette_path = str(tmpdir.join('test.yml'))
    with vcr.use_cassette(cassette_path, record_mode='all'):
        urlopen(DEFAULT_URI)
    return cassette_path


@pytest.mark.parametrize("matcher, matching_uri, not_matching_uri", [
    ('uri',
     'http://httpbin.org/get?p1=q1&p2=q2',
     'http://httpbin.org/get?p2=q2&p1=q1'),
    ('scheme',
     'http://google.com/post?a=b',
     'https://httpbin.org/get?p1=q1&p2=q2'),
    ('host',
     'https://httpbin.org/post?a=b',
     'http://google.com/get?p1=q1&p2=q2'),
    ('port',
     'https://google.com:80/post?a=b',
     'http://httpbin.org:5000/get?p1=q1&p2=q2'),
    ('path',
     'https://google.com/get?a=b',
     'http://httpbin.org/post?p1=q1&p2=q2'),
    ('query',
     'https://google.com/get?p2=q2&p1=q1',
     'http://httpbin.org/get?p1=q1&a=b')
])
def test_matchers(cassette, matcher, matching_uri, not_matching_uri):
    # play cassette with default uri
    with vcr.use_cassette(cassette, match_on=[matcher]) as cass:
        urlopen(DEFAULT_URI)
        assert cass.play_count == 1

    # play cassette with matching on uri
    with vcr.use_cassette(cassette, match_on=[matcher]) as cass:
        urlopen(matching_uri)
        assert cass.play_count == 1

    # play cassette with not matching on uri, it should fail
    with pytest.raises(vcr.errors.CannotOverwriteExistingCassetteException):
        with vcr.use_cassette(cassette, match_on=[matcher]) as cass:
            urlopen(not_matching_uri)


def test_method_matcher(cassette):
    # play cassette with matching on method
    with vcr.use_cassette(cassette, match_on=['method']) as cass:
        urlopen('https://google.com/get?a=b')
        assert cass.play_count == 1

    # should fail if method does not match
    with pytest.raises(vcr.errors.CannotOverwriteExistingCassetteException):
        with vcr.use_cassette(cassette, match_on=['method']) as cass:
            # is a POST request
            urlopen(DEFAULT_URI, data=b'')


@pytest.mark.parametrize("uri", [
    DEFAULT_URI,
    'http://httpbin.org/get?p2=q2&p1=q1',
    'http://httpbin.org/get?p2=q2&p1=q1',
])
def test_default_matcher_matches(cassette, uri):
    with vcr.use_cassette(cassette) as cass:
        urlopen(uri)
        assert cass.play_count == 1


@pytest.mark.parametrize("uri", [
    'https://httpbin.org/get?p1=q1&p2=q2',
    'http://google.com/get?p1=q1&p2=q2',
    'http://httpbin.org:5000/get?p1=q1&p2=q2',
    'http://httpbin.org/post?p1=q1&p2=q2',
    'http://httpbin.org/get?p1=q1&a=b'
])
def test_default_matcher_does_not_match(cassette, uri):
    with pytest.raises(vcr.errors.CannotOverwriteExistingCassetteException):
        with vcr.use_cassette(cassette):
            urlopen(uri)


def test_default_matcher_does_not_match_on_method(cassette):
    with pytest.raises(vcr.errors.CannotOverwriteExistingCassetteException):
        with vcr.use_cassette(cassette):
            # is a POST request
            urlopen(DEFAULT_URI, data=b'')
