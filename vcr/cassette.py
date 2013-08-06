'''The container for recorded requests and responses'''

import os
import tempfile

# Internal imports
from .patch import install, reset
from .files import load_cassette, save_cassette


class Cassette(object):
    '''A container for recorded requests and responses'''
    # TODO: clean up the constructor and
    # classmethods

    @classmethod
    def load(cls, path):
        '''Load in the cassette stored at the provided path'''
        try:
            return cls(path, load_cassette(path))
        except IOError:
            return cls(path)

    def __init__(self, path, data=None):
        self._path = path
        self._requests = []
        self._responses = []
        self.play_count = 0
        if data:
            self.deserialize(data)

    def save(self, path):
        '''Save this cassette to a path'''
        save_cassette(path, self.serialize())

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

    def mark_played(self, request=None):
        '''
        Alert the cassette of a request that's been played
        '''
        self.play_count += 1

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
            #todo: keyerror if not in cassette
            return None

    def __enter__(self):
        '''Patch the fetching libraries we know about'''
        #TODO: how is this context manager used?
        install(self)
        return self

    def __exit__(self, typ, value, traceback):
        self.save(self._path)
        reset()
