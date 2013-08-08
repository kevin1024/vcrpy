'''The container for recorded requests and responses'''

import os
import tempfile

# Internal imports
from .patch import install, reset
from .files import load_cassette, save_cassette
from .request import Request


class Cassette(object):
    '''A container for recorded requests and responses'''
    @classmethod
    def load(cls, path):
        '''Load in the cassette stored at the provided path'''
        try:
            return cls(path, load_cassette(path))
        except IOError:
            return cls(path)

    def __init__(self, path, data=None):
        self._path = path
        self.requests = {}
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
        } for req, res in self.requests.iteritems()])

    def deserialize(self, source):
        '''Given a serialized version, load the requests'''
        for r in source:
            self.requests[r['request']] = r['response']

    def mark_played(self, request=None):
        '''
        Alert the cassette of a request that's been played
        '''
        self.play_count += 1

    def append(self, request, response):
        '''Add a pair of request, response to this cassette'''
        self.requests[request] = response

    def __len__(self):
        '''Return the number of request / response pairs stored in here'''
        return len(self.requests)

    def __contains__(self, request):
        '''Return whether or not a request has been stored'''
        return request in self.requests

    def response(self, request):
        '''Find the response corresponding to a request'''
        return self.requests[request]

    def __enter__(self):
        '''Patch the fetching libraries we know about'''
        install(self)
        return self

    def __exit__(self, typ, value, traceback):
        self.save(self._path)
        reset()
