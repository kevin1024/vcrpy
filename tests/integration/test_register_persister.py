# -*- coding: utf-8 -*-
'''Tests for cassettes with custom persistence'''

# External imports
import os
from six.moves.urllib.request import urlopen

# Internal imports
import vcr
from vcr.persisters.filesystem import FilesystemPersister


def test_save_cassette_with_custom_persister(tmpdir, httpbin):
    '''Ensure you can save a cassette using custom persister'''
    my_vcr = vcr.VCR()
    my_vcr.register_persister(FilesystemPersister)

    # Check to make sure directory doesnt exist
    assert not os.path.exists(str(tmpdir.join('nonexistent')))

    # Run VCR to create dir and cassette file using new save_cassette callback
    with my_vcr.use_cassette(str(tmpdir.join('nonexistent', 'cassette.yml'))):
        urlopen(httpbin.url).read()

    # Callback should have made the file and the directory
    assert os.path.exists(str(tmpdir.join('nonexistent', 'cassette.yml')))


def test_load_cassette_with_custom_persister(tmpdir, httpbin):
    '''
    Ensure you can load a cassette using custom persister
    '''
    my_vcr = vcr.VCR()
    my_vcr.register_persister(FilesystemPersister)

    test_fixture = str(tmpdir.join('synopsis.json'))

    with my_vcr.use_cassette(test_fixture, serializer='json'):
        response = urlopen(httpbin.url).read()
        assert b'difficult sometimes' in response
