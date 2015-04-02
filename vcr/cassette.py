"""The container for recorded requests and responses"""
import logging

import contextlib2
import wrapt
try:
    from collections import Counter
except ImportError:
    from backport_collections import Counter

# Internal imports
from .patch import CassettePatcherBuilder
from .persist import load_cassette, save_cassette
from .serializers import yamlserializer
from .matchers import requests_match, uri, method
from .errors import UnhandledHTTPRequestError


log = logging.getLogger(__name__)


class CassetteContextDecorator(object):
    """Context manager/decorator that handles installing the cassette and
    removing cassettes.

    This class defers the creation of a new cassette instance until the point at
    which it is installed by context manager or decorator. The fact that a new
    cassette is used with each application prevents the state of any cassette
    from interfering with another.
    """

    @classmethod
    def from_args(cls, cassette_class, path, **kwargs):
        return cls(cassette_class, lambda: (path, kwargs))

    def __init__(self, cls, args_getter):
        self.cls = cls
        self._args_getter = args_getter
        self.__finish = None

    def _patch_generator(self, cassette):
        with contextlib2.ExitStack() as exit_stack:
            for patcher in CassettePatcherBuilder(cassette).build():
                exit_stack.enter_context(patcher)
            log.debug('Entered context for cassette at {0}.'.format(cassette._path))
            yield cassette
            log.debug('Exiting context for cassette at {0}.'.format(cassette._path))
            # TODO(@IvanMalison): Hmmm. it kind of feels like this should be
            # somewhere else.
            cassette._save()

    def __enter__(self):
        assert self.__finish is None, "Cassette already open."
        path, kwargs = self._args_getter()
        self.__finish = self._patch_generator(self.cls.load(path, **kwargs))
        return next(self.__finish)

    def __exit__(self, *args):
        next(self.__finish, None)
        self.__finish = None

    @wrapt.decorator
    def __call__(self, function, instance, args, kwargs):
        with self as cassette:
            if cassette.inject:
                return function(cassette, *args, **kwargs)
            else:
                return function(*args, **kwargs)


class Cassette(object):
    """A container for recorded requests and responses"""

    @classmethod
    def load(cls, path, **kwargs):
        """Instantiate and load the cassette stored at the specified path."""
        new_cassette = cls(path, **kwargs)
        new_cassette._load()
        return new_cassette

    @classmethod
    def use_arg_getter(cls, arg_getter):
        return CassetteContextDecorator(cls, arg_getter)

    @classmethod
    def use(cls, *args, **kwargs):
        return CassetteContextDecorator.from_args(cls, *args, **kwargs)

    def __init__(self, path, serializer=yamlserializer, record_mode='once',
                 match_on=(uri, method),  before_record_request=None,
                 before_record_response=None, custom_patches=(),
                 inject=False):

        self._path = path
        self._serializer = serializer
        self._match_on = match_on
        self._before_record_request = before_record_request or (lambda x: x)
        self._before_record_response = before_record_response or (lambda x: x)
        self.inject = inject
        self.record_mode = record_mode
        self.custom_patches = custom_patches

        # self.data is the list of (req, resp) tuples
        self.data = []
        self.play_counts = Counter()
        self.dirty = False
        self.rewound = False

    @property
    def play_count(self):
        return sum(self.play_counts.values())

    @property
    def all_played(self):
        """Returns True if all responses have been played, False otherwise."""
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

    def append(self, request, response):
        """Add a request, response pair to this cassette"""
        request = self._before_record_request(request)
        if not request:
            return
        if self._before_record_response:
            response = self._before_record_response(response)
        self.data.append((request, response))
        self.dirty = True

    def filter_request(self, request):
        return self._before_record_request(request)

    def _responses(self, request):
        """
        internal API, returns an iterator with all responses matching
        the request.
        """
        request = self._before_record_request(request)
        for index, (stored_request, response) in enumerate(self.data):
            if requests_match(request, stored_request, self._match_on):
                yield index, response

    def can_play_response_for(self, request):
        request = self._before_record_request(request)
        return request and request in self and \
            self.record_mode != 'all' and \
            self.rewound

    def play_response(self, request):
        """
        Get the response corresponding to a request, but only if it
        hasn't been played back before, and mark it as played
        """
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
        """
        Find the responses corresponding to a request.
        This function isn't actually used by VCR internally, but is
        provided as an external API.
        """
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
        """Return the number of request,response pairs stored in here"""
        return len(self.data)

    def __contains__(self, request):
        """Return whether or not a request has been stored"""
        for index, response in self._responses(request):
            if self.play_counts[index] == 0:
                return True
        return False
