import os
import json
import urllib2
import vcr

def test_set_serializer_default_config(tmpdir):
    my_vcr = vcr.VCR(serializer='json')

    with my_vcr.use_cassette(str(tmpdir.join('test.json'))):
        assert my_vcr.serializer == 'json'
        urllib2.urlopen('http://httpbin.org/get')

    with open(str(tmpdir.join('test.json'))) as f:
        assert json.loads(f.read())

def test_default_set_cassette_library_dir(tmpdir):
    my_vcr = vcr.VCR(cassette_library_dir=str(tmpdir.join('subdir')))

    with my_vcr.use_cassette('test.json'):
        urllib2.urlopen('http://httpbin.org/get')

    assert os.path.exists(str(tmpdir.join('subdir').join('test.json')))

def test_override_set_cassette_library_dir(tmpdir):
    my_vcr = vcr.VCR(cassette_library_dir=str(tmpdir.join('subdir')))

    with my_vcr.use_cassette('test.json', cassette_library_dir=str(tmpdir.join('subdir2'))):
        urllib2.urlopen('http://httpbin.org/get')

    assert os.path.exists(str(tmpdir.join('subdir2').join('test.json')))
    assert not os.path.exists(str(tmpdir.join('subdir').join('test.json')))

