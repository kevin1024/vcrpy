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


class Cassette(object):
    '''A container for recorded requests and responses'''
    @classmethod
    def load(cls, path, **kwargs):
        '''Load in the cassette stored at the provided path'''
        new_cassette = cls(path, **kwargs)
        new_cassette._load()
        return new_cassette

    def __init__(self, path, serializer=yamlserializer):
        self._path = path
        self._serializer = serializer
        self.data = OrderedDict()
        self.play_counts = Counter()
        self.dirty = False

    @property
    def play_count(self):
        return sum(self.play_counts.values())

    @property
    def requests(self):
        return self.data.keys()

    @property
    def responses(self):
        return self.data.values()

    def mark_played(self, request):
        '''
        Alert the cassette of a request that's been played
        '''
        self.play_counts[request] += 1

    def append(self, request, response):
        '''Add a request, response pair to this cassette'''
        self.data[request] = response
        self.dirty = True

    def response_of(self, request):
        '''Find the response corresponding to a request'''
        return self.data[request]

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
        return request in self.data

    def __enter__(self):
        '''Patch the fetching libraries we know about'''
        install(self)
        return self

    def __exit__(self, typ, value, traceback):
        self._save()
        reset()
