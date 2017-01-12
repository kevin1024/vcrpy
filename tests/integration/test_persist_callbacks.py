# -*- coding: utf-8 -*-
'''Tests for cassettes with overriden persistence'''

# External imports
import os
from six.moves.urllib.request import urlopen

# Internal imports
import vcr
from vcr.persisters.filesystem import FilesystemPersister


def test_overriding_save_cassette_with_callback(tmpdir, httpbin):
    '''Ensure you can save a cassette using save_callback'''

    def save_callback(cassette_path, data):
        FilesystemPersister.write(cassette_path, data)

    # Check to make sure directory doesnt exist
    assert not os.path.exists(str(tmpdir.join('nonexistent')))

    # Run VCR to create dir and cassette file using new save_cassette callback
    with vcr.use_cassette(
            str(tmpdir.join('nonexistent', 'cassette.yml')),
            save_callback=save_callback
    ):
        urlopen(httpbin.url).read()

    # Callback should have made the file and the directory
    assert os.path.exists(str(tmpdir.join('nonexistent', 'cassette.yml')))


def test_overriding_load_cassette_with_callback(tmpdir, httpbin):
    '''
    Ensure you can load a cassette using load_callback
    '''
    test_fixture = str(tmpdir.join('synopsis.json'))

    def load_callback(cassette_path):
        with open(cassette_path) as f:
            cassette_content = f.read()
        return cassette_content

    with vcr.use_cassette(
            test_fixture,
            serializer='json',
            load_callback=load_callback
    ):
        response = urlopen(httpbin.url).read()
        assert b'difficult sometimes' in response
