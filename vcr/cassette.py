'''The container for recorded requests and responses'''
import functools
try:
    from collections import Counter
except ImportError:
    from .compat.counter import Counter

# Internal imports
from .patch import install, reset
from .persist import load_cassette, save_cassette
from .filters import filter_request
from .serializers import yamlserializer
from .matchers import requests_match, uri, method
from .errors import UnhandledHTTPRequestError


class use_cassette(object):

    def __init__(self, cls, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.cls = cls

    def __enter__(self):
        self._cassette = self.cls.load(*self.args, **self.kwargs)
        return self._cassette.__enter__()

    def __exit__(self, *args):
        return self._cassette.__exit__(*args)

    def __call__(self, function):
        @functools.wraps(function)
        def wrapped(*args, **kwargs):
            with self:
                return function(*args, **kwargs)
        return wrapped


class Cassette(object):
    '''A container for recorded requests and responses'''

    @classmethod
    def load(cls, path, **kwargs):
        '''Load in the cassette stored at the provided path'''
        new_cassette = cls(path, **kwargs)
        new_cassette._load()
        return new_cassette

    @classmethod
    def use_cassette(cls, *args, **kwargs):
        return use_cassette(cls, *args, **kwargs)

    def __init__(self,
                 path,
                 serializer=yamlserializer,
                 record_mode='once',
                 match_on=(uri, method),
                 filter_headers=(),
                 filter_query_parameters=(),
                 before_record=None,
                 ignore_hosts=(),
                 ignore_localhost=()
                 ):
        self._path = path
        self._serializer = serializer
        self._match_on = match_on
        self._filter_headers = filter_headers
        self._filter_query_parameters = filter_query_parameters
        self._before_record = before_record
        self._ignore_hosts = ignore_hosts
        if ignore_localhost:
            self._ignore_hosts = list(set(
                self._ignore_hosts + ['localhost', '0.0.0.0', '127.0.0.1']
            ))

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
    def all_played(self):
        """
        Returns True if all responses have been played, False otherwise.
        """
        return self.play_count == len(self)

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

    def _filter_request(self, request):
        return filter_request(
            request=request,
            filter_headers=self._filter_headers,
            filter_query_parameters=self._filter_query_parameters,
            before_record=self._before_record,
            ignore_hosts=self._ignore_hosts
        )

    def append(self, request, response):
        '''Add a request, response pair to this cassette'''
        request = self._filter_request(request)
        if not request:
            return
        self.data.append((request, response))
        self.dirty = True

    def _responses(self, request):
        """
        internal API, returns an iterator with all responses matching
        the request.
        """
        request = self._filter_request(request)
        if not request:
            return
        for index, (stored_request, response) in enumerate(self.data):
            if requests_match(request, stored_request, self._match_on):
                yield index, response

    def can_play_response_for(self, request):
        request = self._filter_request(request)
        return request and request in self and \
            self.record_mode != 'all' and \
            self.rewound

    def play_response(self, request):
        '''
        Get the response corresponding to a request, but only if it
        hasn't been played back before, and mark it as played
        '''
        for index, response in self._responses(request):
            if self.play_counts[index] == 0:
                self.play_counts[index] += 1
                return response
        # The cassette doesn't contain the request asked for.
        raise UnhandledHTTPRequestError(
            "The cassette (%r) doesn't contain the request (%r) asked for"
            % (self._path, request)
        )

    def responses_of(self, request):
        '''
        Find the responses corresponding to a request.
        This function isn't actually used by VCR internally, but is
        provided as an external API.
        '''
        responses = [response for index, response in self._responses(request)]

        if responses:
            return responses
        # The cassette doesn't contain the request asked for.
        raise UnhandledHTTPRequestError(
            "The cassette (%r) doesn't contain the request (%r) asked for"
            % (self._path, request)
        )

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
        for response in self._responses(request):
            return True
        return False

    def __enter__(self):
        '''Patch the fetching libraries we know about'''
        install(self)
        return self

    def __exit__(self, typ, value, traceback):
        self._save()
        reset()
