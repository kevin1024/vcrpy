'''The container for recorded requests and responses'''

try:
    from collections import Counter, OrderedDict
except ImportError:
    from .compat.counter import Counter
    from .compat.ordereddict import OrderedDict

# Internal imports
from .patch import install, reset
from .persist import load_cassette, save_cassette
from .serializers import yamlserializer
from .matchers import requests_match, url, method


class Cassette(object):
    '''A container for recorded requests and responses'''

    @classmethod
    def load(cls, path, **kwargs):
        '''Load in the cassette stored at the provided path'''
        new_cassette = cls(path, **kwargs)
        new_cassette._load()
        return new_cassette

    def __init__(self,
                 path,
                 serializer=yamlserializer,
                 record_mode='once',
                 match_on=[url, method]):
        self._path = path
        self._serializer = serializer
        self._match_on = match_on

        # self.data is the list of (req, resp) tuples
        self.data = []
        self.play_counts = Counter()
        self.dirty = False
        self.rewound = False
        self.record_mode = record_mode

    @property
    def play_count(self):
        return sum(self.play_counts.values())

    @property
    def requests(self):
        return [request for (request, response) in self.data]

    @property
    def responses(self):
        return [response for (request, response) in self.data]

    @property
    def write_protected(self):
        return self.rewound and self.record_mode == 'once' or \
            self.record_mode == 'none'

    def append(self, request, response):
        '''Add a request, response pair to this cassette'''
        self.data.append((request, response))
        self.dirty = True

    def response_of(self, request):
        '''
        Find the response corresponding to a request

        '''
        for index, (stored_request, response) in enumerate(self.data):
            if requests_match(request, stored_request, self._match_on):
                if self.play_counts[index] == 0:
                    self.play_counts[index] += 1
                    return response
        # I decided that a KeyError is the best exception to raise
        # if the cassette doesn't contain the request asked for.
        raise KeyError

    def _as_dict(self):
        return {"requests": self.requests, "responses": self.responses}

    def _save(self, force=False):
        if force or self.dirty:
            save_cassette(
                self._path,
                self._as_dict(),
                serializer=self._serializer
            )
            self.dirty = False

    def _load(self):
        try:
            requests, responses = load_cassette(
                self._path,
                serializer=self._serializer
            )
            for request, response in zip(requests, responses):
                self.append(request, response)
            self.dirty = False
            self.rewound = True
        except IOError:
            pass

    def __str__(self):
        return "<Cassette containing {0} recorded response(s)>".format(
            len(self)
        )

    def __len__(self):
        '''Return the number of request,response pairs stored in here'''
        return len(self.data)

    def __contains__(self, request):
        '''Return whether or not a request has been stored'''
        for stored_request, response in self.data:
            if requests_match(stored_request, request, self._match_on):
                return True
        return False

    def __enter__(self):
        '''Patch the fetching libraries we know about'''
        install(self)
        return self

    def __exit__(self, typ, value, traceback):
        self._save()
        reset()
