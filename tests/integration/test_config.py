import json
import urllib2
import vcr

def test_set_serializer_default_config(tmpdir):
    my_vcr = vcr.VCR(serializer='json')

    with my_vcr.use_cassette(str(tmpdir.join('test.json'))) as cass:
        assert my_vcr.serializer == 'json'
        urllib2.urlopen('http://httpbin.org/get')

    with open(str(tmpdir.join('test.json'))) as f:
        assert json.loads(f.read())

