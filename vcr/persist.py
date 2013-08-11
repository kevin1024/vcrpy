import tempfile
import os
import yaml

# Use the libYAML versions if possible
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

def _serialize_cassette(requests, responses):
    '''Return a serializable version of the cassette'''
    return ([{
        'request': request,
        'response': response,
    } for request, response in zip(requests, responses)])

def _deserialize_cassette(data):
    requests = [r['request'] for r in data]
    responses = [r['response'] for r in data]
    return requests, responses

def _secure_write(path, contents):
    """
    We'll overwrite the old version securely by writing out a temporary
    version and then moving it to replace the old version
    """
    dirname, filename = os.path.split(path)
    fd, name = tempfile.mkstemp(dir=dirname, prefix=filename)
    with os.fdopen(fd, 'w') as fout:
        fout.write(contents)
        os.rename(name, path)

def load_cassette(cassette_path):
    data =  yaml.load(open(cassette_path), Loader=Loader)
    return _deserialize_cassette(data)

def save_cassette(cassette_path, requests, responses):
    dirname, filename = os.path.split(cassette_path)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname)
    data = _serialize_cassette(requests, responses)
    data = yaml.dump(data, Dumper=Dumper)
    _secure_write(cassette_path, data)
