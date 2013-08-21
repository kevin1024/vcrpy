'''Basic tests about cassettes'''
# coding=utf-8

# External imports
import os
import urllib2

# Internal imports
import vcr

def test_nonexistent_directory(tmpdir):
    '''If we load a cassette in a nonexistent directory, it can save ok'''
    # Check to make sure directory doesnt exist
    assert not os.path.exists(str(tmpdir.join('nonexistent')))

    # Run VCR to create dir and cassette file
    with vcr.use_cassette(str(tmpdir.join('nonexistent','cassette.yml'))):
        urllib2.urlopen('http://httpbin.org/').read()

    # This should have made the file and the directory
    assert os.path.exists(str(tmpdir.join('nonexistent','cassette.yml')))

def test_unpatch(tmpdir):
    '''Ensure that our cassette gets unpatched when we're done'''
    with vcr.use_cassette(str(tmpdir.join('unpatch.yaml'))) as cass:
        urllib2.urlopen('http://httpbin.org/').read()

    # Make the same request, and assert that we haven't served any more
    # requests out of cache
    urllib2.urlopen('http://httpbin.org/').read()
    assert cass.play_count == 0

def test_basic_use(tmpdir):
    '''
    Copied from the docs 
    '''
    with vcr.use_cassette('fixtures/vcr_cassettes/synopsis.yaml'):
        response = urllib2.urlopen('http://www.iana.org/domains/reserved').read()
        assert 'Example domains' in response

def test_basic_json_use(tmpdir):
    '''Ensure you can load a json serialized cassette'''
    with vcr.use_cassette('fixtures/vcr_cassettes/synopsis.json', serializer='json'):
        response = urllib2.urlopen('http://www.iana.org/domains/reserved').read()
        assert 'Example domains' in response

def test_patched_content(tmpdir):
    '''Ensure that what you pull from a cassette is what came from the request'''
    with vcr.use_cassette(str(tmpdir.join('synopsis.yaml'))) as cass:
        response = urllib2.urlopen('http://www.iana.org/domains/reserved').read()
        assert cass.play_count == 0

    with vcr.use_cassette(str(tmpdir.join('synopsis.yaml'))) as cass:
        response2= urllib2.urlopen('http://www.iana.org/domains/reserved').read()
        assert cass.play_count == 1

    with vcr.use_cassette(str(tmpdir.join('synopsis.yaml'))) as cass:
        response3= urllib2.urlopen('http://www.iana.org/domains/reserved').read()
        assert cass.play_count == 1

    assert response == response2
    assert response2 == response3

def test_patched_content_json(tmpdir):
    '''Ensure that what you pull from a json cassette is what came from the request'''
    with vcr.use_cassette(str(tmpdir.join('synopsis.json')), serializer='json') as cass:
        response = urllib2.urlopen('http://www.iana.org/domains/reserved').read()
        assert cass.play_count == 0

    with vcr.use_cassette(str(tmpdir.join('synopsis.json')), serializer='json') as cass:
        response2= urllib2.urlopen('http://www.iana.org/domains/reserved').read()
        assert cass.play_count == 1

    with vcr.use_cassette(str(tmpdir.join('synopsis.json')), serializer='json') as cass:
        response3= urllib2.urlopen('http://www.iana.org/domains/reserved').read()
        assert cass.play_count == 1

    assert response == response2
    assert response2 == response3
