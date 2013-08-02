'''The container for recorded requests and responses'''

import os
import yaml
import tempfile
try:
    # Use the libYAML versions if possible. They're much faster than the pure
    # python implemenations
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:  # pragma: no cover
    from yaml import Loader, Dumper

# Internal imports
from .patch import install, reset


class Cassette(object):
    '''A container for recorded requests and responses'''
    @classmethod
    def load(cls, path):
        '''Load in the cassette stored at the provided path'''
        try:
            with open(path) as fin:
                return cls(path, yaml.load(fin, Loader=Loader))
        except IOError:
            return cls(path)

    def __init__(self, path, data=None):
        self._path = path
        self._cached = []
        self._requests = []
        self._responses = []
        if data:
            self.deserialize(data)

    def save(self, path):
        '''Save this cassette to a path'''
        dirname, filename = os.path.split(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        # We'll overwrite the old version securely by writing out a temporary
        # version and then moving it to replace the old version
        fd, name = tempfile.mkstemp(dir=dirname, prefix=filename)
        with os.fdopen(fd, 'w') as fout:
            fout.write(yaml.dump(self.serialize(), Dumper=Dumper))
        os.rename(name, path)

    def serialize(self):
        '''Return a serializable version of the cassette'''
        return ([{
            'request': req,
            'response': res,
        } for req, res in zip(self._requests, self._responses)])

    def deserialize(self, source):
        '''Given a seritalized version, load the requests'''
        self._requests, self._responses = (
            [r['request'] for r in source], [r['response'] for r in source])

    def cached(self, request=None):
        '''Alert the cassete of a request that's been cached, or get the
        requests that we've cached'''
        if request:
            self._cached.append(request)
        else:
            return self._cached

    def append(self, request, response):
        '''Add a pair of request, response pairs to this cassette'''
        self._requests.append(request)
        self._responses.append(response)

    def __len__(self):
        '''Return the number of request / response pairs stored in here'''
        return len(self._requests)

    def __contains__(self, request):
        '''Return whether or not a request has been stored'''
        try:
            self._requests.index(request)
            return True
        except ValueError:
            return False

    def response(self, request):
        '''Find the response corresponding to a request'''
        try:
            return self._responses[self._requests.index(request)]
        except ValueError:
            return None

    def __enter__(self):
        '''Patch the fetching libraries we know about'''
        install(self)
        return self

    def __exit__(self, typ, value, traceback):
        self.save(self._path)
        reset()
