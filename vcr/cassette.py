from __future__ import annotations

import collections
import contextlib
import copy
import inspect
import logging
import sys
from collections.abc import Callable, Generator, Iterable, Iterator, Sequence
from inspect import iscoroutinefunction
from types import TracebackType
from typing import TYPE_CHECKING, Concatenate, Generic, ParamSpec, Protocol, Self, Unpack

import wrapt

from ._handle_coroutine import handle_coroutine
from .errors import MissingMetadataError, UnhandledHTTPRequestError
from .filters import sensitive_data_hooks
from .matchers import get_matchers_results, method, requests_match, uri
from .patch import CassettePatcherBuilder, validate_skip_patchers
from .persisters.filesystem import CassetteDecodeError, CassetteNotFoundError, FilesystemPersister
from .record_mode import RecordMode, validate_record_mode
from .serializers import yamlserializer
from .util import as_list

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

if sys.version_info >= (3, 13):
    from typing import TypeVar
else:
    from typing_extensions import TypeVar

if TYPE_CHECKING:
    from typing_extensions import TypeIs

    from .request import Request
    from .types import (
        JSON,
        CassetteArgs,
        CassetteConfig,
        CassetteDict,
        CustomPatch,
        Interaction,
        InteractionHook,
        Matcher,
        MatcherFailure,
        Metadata,
        OneOrMany,
        PatcherName,
        Persister,
        RecordModeLike,
        RequestFilter,
        Response,
        ResponseFilter,
        SensitiveData,
        Serializer,
        SimilarRequest,
        StrPath,
    )

log: logging.Logger = logging.getLogger(__name__)

_P = ParamSpec("_P")
_R = TypeVar("_R")
_J = TypeVar("_J", bound="JSON")
_C = TypeVar("_C", bound="Cassette", default="Cassette")


class CassetteContextDecorator(Generic[_C]):
    """Context manager/decorator that handles installing the cassette and
    removing cassettes.

    This class defers the creation of a new cassette instance until
    the point at which it is installed by context manager or
    decorator. The fact that a new cassette is used with each
    application prevents the state of any cassette from interfering
    with another.

    Instances of this class are NOT reentrant as context managers.
    However, functions that are decorated by
    ``CassetteContextDecorator`` instances ARE reentrant. See the
    implementation of ``__call__`` on this class for more details.
    There is also a guard against attempts to reenter instances of
    this class as a context manager in ``__exit__``.
    """

    @classmethod
    def from_args(
        cls,
        cassette_class: type[_C],
        **kwargs: Unpack[CassetteConfig],
    ) -> CassetteContextDecorator[_C]:
        return cls(cassette_class, kwargs.copy)

    def __init__(self, cls: type[_C], args_getter: Callable[[], CassetteConfig]) -> None:
        self.cls: type[_C] = cls
        self._args_getter: Callable[[], CassetteConfig] = args_getter
        self.__finish: Generator[_C, None, None] | None = None
        self.__cassette: _C | None = None

    def _patch_generator(self, cassette: _C) -> Generator[_C, None, None]:
        with contextlib.ExitStack() as exit_stack:
            for patcher in CassettePatcherBuilder(cassette).build():
                exit_stack.enter_context(patcher)
            log_format = "{action} context for cassette at {path}."
            log.debug(log_format.format(action="Entering", path=cassette._path))
            yield cassette
            log.debug(log_format.format(action="Exiting", path=cassette._path))

    def __enter__(self) -> _C:
        # This assertion is here to prevent the dangerous behavior
        # that would result from forgetting about a __finish before
        # completing it.
        # How might this condition be met? Here is an example:
        # context_decorator = Cassette.use('whatever')
        # with context_decorator:
        #     with context_decorator:
        #         pass
        assert self.__finish is None, "Cassette already open."
        config = self._args_getter()
        if "path" not in config:
            # Only a decorator can name a cassette after its function (#570).
            raise TypeError(
                "use_cassette() needs a path when it's used as a context manager. "
                "It can be left out only when decorating a function, to name the "
                "cassette after the function.",
            )
        path = config["path"]
        transformer = config.get("path_transformer")
        if transformer:
            path = transformer(path)
        cassette = self.cls.load(path=path, **_cassette_args(config))
        self.__cassette = cassette
        self.__finish = self._patch_generator(cassette)
        return next(self.__finish)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        exception_was_raised = exc_type is not None or exc_value is not None or traceback is not None
        record_on_exception = self._args_getter().get("record_on_exception", True)
        if self.__cassette is not None and (record_on_exception or not exception_was_raised):
            self.__cassette._save()
            self.__cassette = None
        # Fellow programmer, don't remove this `next`, if `self.__finish` is
        # not consumed the unpatcher functions accumulated in the `exit_stack`
        # object created in `_patch_generator` will not be called until
        # `exit_stack` is not garbage collected.
        # This works in CPython but not in Pypy, where the unpatchers will not
        # be called until much later.
        if self.__finish is not None:
            next(self.__finish, None)
        self.__finish = None

    def __call__(self, function: Callable[_P, _R]) -> Callable[_P, _R]:
        """Decorate a function, coroutine function or generator function, to run it with a
        new cassette each time it's called."""
        return self._decorate(function)

    @wrapt.decorator
    def _decorate(
        self,
        function: Callable[..., _R],
        instance: object,
        args: tuple[object, ...],
        kwargs: dict[str, object],
    ) -> _R:
        # This awkward cloning thing is done to ensure that decorated
        # functions are reentrant. This is required for thread
        # safety and the correct operation of recursive functions.
        args_getter = self._build_args_getter_for_decorator(function)
        return type(self)(self.cls, args_getter)._execute_function(function, args, kwargs)

    def _execute_function(
        self,
        function: Callable[..., _R],
        args: tuple[object, ...],
        kwargs: dict[str, object],
    ) -> _R:
        def handle_function(cassette: _C) -> _R:
            if cassette.inject:
                return function(cassette, *args, **kwargs)
            else:
                return function(*args, **kwargs)

        if iscoroutinefunction(function):
            return handle_coroutine(vcr=self, fn=handle_function)  # type: ignore[arg-type, return-value]
        if inspect.isgeneratorfunction(function):
            return self._handle_generator(fn=handle_function)  # type: ignore[arg-type, return-value]

        return self._handle_function(fn=handle_function)

    def _handle_generator(
        self,
        fn: Callable[[_C], Generator[object, object, _R]],
    ) -> Generator[object, object, _R]:
        """Wraps a generator so that we're inside the cassette context for the
        duration of the generator.
        """
        with self as cassette:
            return (yield from fn(cassette))

    def _handle_function(self, fn: Callable[[_C], _R]) -> _R:
        with self as cassette:
            return fn(cassette)

    @staticmethod
    def get_function_name(function: Callable[..., object]) -> str:
        name: str = getattr(function, "__name__", repr(function))
        return name

    def _build_args_getter_for_decorator(
        self,
        function: Callable[..., object],
    ) -> Callable[[], CassetteConfig]:
        def new_args_getter() -> CassetteConfig:
            kwargs = self._args_getter()
            if "path" not in kwargs:
                name_generator = kwargs.get("func_path_generator") or self.get_function_name
                path = name_generator(function)
                kwargs["path"] = path
            return kwargs

        return new_args_getter


class Cassette:
    """A container for recorded requests and responses"""

    @classmethod
    def load(cls, *, path: StrPath, **kwargs: Unpack[CassetteArgs]) -> Self:
        """Instantiate and load the cassette stored at the specified path."""
        new_cassette = cls(path, **kwargs)
        new_cassette._load()
        return new_cassette

    @classmethod
    def use_arg_getter(cls, arg_getter: Callable[[], CassetteConfig]) -> CassetteContextDecorator[Self]:
        return CassetteContextDecorator(cls, arg_getter)

    @classmethod
    def use(cls, **kwargs: Unpack[CassetteConfig]) -> CassetteContextDecorator[Self]:
        return CassetteContextDecorator(cls, kwargs.copy)

    def __init__(
        self,
        path: StrPath,
        serializer: Serializer | None = None,
        persister: Persister | None = None,
        record_mode: RecordModeLike = RecordMode.ONCE,
        match_on: Sequence[Matcher] = (uri, method),
        before_record_request: RequestFilter | None = None,
        before_record_response: ResponseFilter | None = None,
        custom_patches: Iterable[CustomPatch] = (),
        inject: bool = False,
        allow_playback_repeats: bool = False,
        drop_unused_requests: bool = False,
        filter_sensitive_data: SensitiveData = (),
        before_save_interaction: OneOrMany[InteractionHook] | None = None,
        after_load_interaction: OneOrMany[InteractionHook] | None = None,
        skip_patchers: Iterable[PatcherName] = (),
    ) -> None:
        self._persister: Persister = persister or FilesystemPersister
        self._path: StrPath = path
        self._serializer: Serializer = serializer or yamlserializer
        self._match_on: Sequence[Matcher] = match_on
        self._before_record_request: RequestFilter = before_record_request or _identity
        log.info(self._before_record_request)
        self._before_record_response: ResponseFilter = before_record_response or _identity
        self.inject: bool = inject
        self.record_mode: RecordMode = validate_record_mode(record_mode)
        self.custom_patches: tuple[CustomPatch, ...] = tuple(custom_patches)
        self.allow_playback_repeats: bool = allow_playback_repeats
        self.drop_unused_requests: bool = drop_unused_requests
        # Hooks run on each interaction as the cassette is saved and loaded.
        # filter_sensitive_data hides values after the user's save hooks and
        # restores them before the user's load hooks, so those see real values.
        self._before_save_interaction: list[InteractionHook] = as_list(before_save_interaction)
        self._after_load_interaction: list[InteractionHook] = as_list(after_load_interaction)
        if filter_sensitive_data:
            hide, restore = sensitive_data_hooks(filter_sensitive_data)
            self._before_save_interaction.append(hide)
            self._after_load_interaction.insert(0, restore)
        self.skip_patchers: tuple[PatcherName, ...] = validate_skip_patchers(skip_patchers)

        # self.data is the list of (req, resp) tuples
        self.data: list[Interaction] = []
        # Values stored with get_metadata, saved in the cassette next to the interactions.
        self._metadata: Metadata = {}
        self.play_counts: collections.Counter[int] = collections.Counter()
        self.dirty: bool = False
        self.rewound: bool = False

        # Subsets of self.data to store old and played interactions
        self._old_interactions: list[Interaction] = []
        self._played_interactions: list[Interaction] = []
        # Number of entries at the start of self.data that came from the file
        self._loaded_count: int = 0

    @property
    def path(self) -> StrPath:
        """The path the cassette is saved to and loaded from."""
        return self._path

    @property
    def play_count(self) -> int:
        return sum(self.play_counts.values())

    @property
    def all_played(self) -> bool:
        """Returns True if all responses have been played, False otherwise."""
        return len(self.play_counts.values()) == len(self)

    @property
    def requests(self) -> list[Request]:
        return [request for (request, response) in self.data]

    @property
    def responses(self) -> list[Response]:
        return [response for (request, response) in self.data]

    @property
    def write_protected(self) -> bool:
        return (self.rewound and self.record_mode == RecordMode.ONCE) or self.record_mode == RecordMode.NONE

    def append(self, request: Request, response: Response) -> None:
        """Add a request, response pair to this cassette"""
        filtered_request = self._before_record_request(request)
        if not filtered_request:
            return
        log.info("Appending request %s and response %s", filtered_request, response)
        # Deepcopy is here because mutation of `response` will corrupt the
        # real response.
        filtered_response = self._before_record_response(copy.deepcopy(response))
        if filtered_response is None:
            return
        self.data.append((filtered_request, filtered_response))
        self.dirty = True

    def filter_request(self, request: Request) -> Request | None:
        return self._before_record_request(request)

    def _responses(self, request: Request) -> Iterator[tuple[int, Response]]:
        """
        internal API, returns an iterator with all responses matching
        the request.
        """
        filtered = self._before_record_request(request)
        if filtered is None:
            return
        for index, (stored_request, response) in enumerate(self.data):
            if requests_match(filtered, stored_request, self._match_on):
                yield index, response

    def can_play_response_for(self, request: Request) -> bool:
        filtered = self._before_record_request(request)
        return bool(
            filtered
            and filtered in self
            and self.record_mode != RecordMode.ALL
            and (self.rewound or self.allow_playback_repeats),
        )

    def play_response(self, request: Request) -> Response:
        """
        Get the response corresponding to a request, but only if it
        hasn't been played back before, and mark it as played
        """
        for index, response in self._responses(request):
            if self.play_counts[index] == 0 or self.allow_playback_repeats:
                # Remember each loaded interaction once, however often it's played,
                # for drop_unused_requests. Interactions recorded now are saved anyway.
                if self.play_counts[index] == 0 and index < self._loaded_count:
                    # Use stored (possibly modified) request, not the raw incoming request
                    self._played_interactions.append((self.data[index][0], response))
                self.play_counts[index] += 1
                return response
        # The cassette doesn't contain the request asked for.
        raise UnhandledHTTPRequestError(
            f"The cassette ({self._path!r}) doesn't contain the request ({request!r}) asked for",
        )

    def responses_of(self, request: Request) -> list[Response]:
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
            f"The cassette ({self._path!r}) doesn't contain the request ({request!r}) asked for",
        )

    def rewind(self) -> None:
        self.play_counts = collections.Counter()

    def find_requests_with_most_matches(self, request: Request) -> list[SimilarRequest]:
        """
        Get the most similar request(s) stored in the cassette
        of a given request as a list of tuples like this:
        - the request object
        - the successful matchers as string
        - the failed matchers and the related assertion message with the difference details as strings tuple

        This is useful when a request failed to be found,
        we can get the similar request(s) in order to know what have changed in the request parts.
        """
        best_matches: list[tuple[int, Request, list[str], list[MatcherFailure]]] = []
        filtered = self._before_record_request(request)
        if filtered is None:
            return []
        for stored_request, _ in self.data:
            successes, fails = get_matchers_results(filtered, stored_request, self._match_on)
            best_matches.append((len(successes), stored_request, successes, fails))
        best_matches.sort(key=lambda t: t[0], reverse=True)
        # Get the first best matches (multiple if equal matches)
        final_best_matches: list[SimilarRequest] = []

        if not best_matches:
            return final_best_matches

        previous_nb_success = best_matches[0][0]
        for best_match in best_matches:
            nb_success = best_match[0]
            # Do not keep matches that have 0 successes,
            # it means that the request is totally different from
            # the ones stored in the cassette
            if nb_success < 1 or previous_nb_success != nb_success:
                break
            previous_nb_success = nb_success
            final_best_matches.append((best_match[1], best_match[2], best_match[3]))

        return final_best_matches

    def get_metadata(self, key: str, default: _J) -> JSON | _J:
        """Return the value stored in the cassette under key.

        If the cassette has no such value, store default and return it, or
        raise MissingMetadataError if the record mode doesn't allow changing
        the cassette. A stored value is what the cassette holds, which needn't
        have the type of default, so check it before relying on that.
        """
        if key in self._metadata:
            return self._metadata[key]
        if self.write_protected:
            raise MissingMetadataError(cassette=self, key=key)
        self._metadata[key] = default
        self.dirty = True
        return default

    def _new_interactions(self) -> list[Interaction]:
        """List of new HTTP interactions (request/response tuples)"""
        new_interactions: list[Interaction] = []
        for request, response in self.data:
            if all(
                not requests_match(request, old_request, self._match_on)
                for old_request, _ in self._old_interactions
            ):
                new_interactions.append((request, response))
        return new_interactions

    def _as_dict(self) -> CassetteDict:
        return {"requests": self.requests, "responses": self.responses}

    def _build_used_interactions_dict(self) -> CassetteDict:
        interactions = self._played_interactions + self._new_interactions()
        cassete_dict: CassetteDict = {
            "requests": [request for request, _ in interactions],
            "responses": [response for _, response in interactions],
        }
        return cassete_dict

    def _rerecorded_interactions(self) -> list[Interaction]:
        """Interactions to save in "all" mode.

        Interactions recorded now replace the loaded ones they match, so
        re-recording doesn't duplicate them. Loaded interactions that weren't
        re-recorded are kept, unless drop_unused_requests is set.
        """
        loaded = self.data[: self._loaded_count]
        recorded = self.data[self._loaded_count :]
        if self.drop_unused_requests:
            return recorded
        kept = [
            (old_request, old_response)
            for old_request, old_response in loaded
            if not any(requests_match(request, old_request, self._match_on) for request, _ in recorded)
        ]
        return kept + recorded

    def _save(self, force: bool = False) -> None:
        if self.record_mode == RecordMode.ALL:
            if force or self.dirty:
                interactions = self._rerecorded_interactions()
                cassete_dict: CassetteDict = {
                    "requests": [request for request, _ in interactions],
                    "responses": [response for _, response in interactions],
                }
                self._persist(cassete_dict)
                self.dirty = False
            return
        if self.drop_unused_requests and len(self._played_interactions) < len(self._old_interactions):
            cassete_dict = self._build_used_interactions_dict()
            force = True
        else:
            cassete_dict = self._as_dict()
        if force or self.dirty:
            self._persist(cassete_dict)
            self.dirty = False

    def _persist(self, cassette_dict: CassetteDict) -> None:
        if self._before_save_interaction:
            interactions: list[Interaction] = []
            for request, response in zip(cassette_dict["requests"], cassette_dict["responses"], strict=True):
                # Hooks get copies, so they can't change the interactions in memory.
                interaction = _run_hooks(
                    self._before_save_interaction,
                    copy.deepcopy(request),
                    copy.deepcopy(response),
                    self,
                )
                if interaction is not None:
                    interactions.append(interaction)
            cassette_dict = {
                "requests": [request for request, _ in interactions],
                "responses": [response for _, response in interactions],
            }
        if self._metadata:
            cassette_dict = {**cassette_dict, "metadata": self._metadata}
        self._persister.save_cassette(self._path, cassette_dict, serializer=self._serializer)

    def _load(self) -> None:
        try:
            # Persisters return (requests, responses), and metadata third if the cassette has any.
            loaded = self._persister.load_cassette(self._path, serializer=self._serializer)
            requests, responses = loaded[0], loaded[1]
            for request, response in zip(requests, responses, strict=False):
                interaction = _run_hooks(self._after_load_interaction, request, response, self)
                if interaction is None:
                    continue
                request, response = interaction
                self.append(request, response)
                self._old_interactions.append((request, response))
            self._loaded_count = len(self.data)
            self.dirty = False
            self.rewound = True
            self._metadata = loaded[2] if len(loaded) == 3 else {}
        except CassetteNotFoundError:
            pass
        except CassetteDecodeError:
            # Unlike a missing cassette, this one exists, so say why it's treated as empty (#501).
            log.warning(
                "Cassette %s exists but couldn't be loaded, so it's treated as empty, "
                "and recording may overwrite it.",
                self._path,
                exc_info=True,
            )

    @override
    def __str__(self) -> str:
        return f"<Cassette containing {len(self)} recorded response(s)>"

    def __len__(self) -> int:
        """Return the number of request,response pairs stored in here"""
        return len(self.data)

    def __contains__(self, request: Request) -> bool:
        """Return whether or not a request has been stored"""
        for index, _ in self._responses(request):
            if self.play_counts[index] == 0 or self.allow_playback_repeats:
                return True
        return False


def _accepts_cassette(
    hook: InteractionHook,
) -> TypeIs[Callable[[Request, Response, Cassette], Interaction | None]]:
    """Whether an interaction hook takes the cassette as a third argument."""
    try:
        inspect.signature(hook).bind(None, None, None)
    except (TypeError, ValueError):
        return False
    return True


def _takes_request_and_response(
    hook: InteractionHook,
) -> TypeIs[Callable[[Request, Response], Interaction | None]]:
    """Whether an interaction hook can be called with the request and response.

    A hook whose signature can't be inspected is assumed to.
    """
    try:
        inspect.signature(hook).bind(None, None)
    except TypeError:
        return False
    except ValueError:
        return True
    return True


def _run_hooks(
    hooks: Iterable[InteractionHook],
    request: Request,
    response: Response,
    cassette: Cassette,
) -> Interaction | None:
    """Run interaction hooks in order. Returns None if one of them drops the interaction.

    Hooks are called with the request and response, and with the cassette
    too if they accept a third argument.
    """
    for hook in hooks:
        if _accepts_cassette(hook):
            interaction = hook(request, response, cassette)
        elif _takes_request_and_response(hook):
            interaction = hook(request, response)
        else:
            # A hook of untyped code may take neither.
            name = getattr(hook, "__qualname__", repr(hook))  # type: ignore[unreachable]
            raise TypeError(
                f"Interaction hook {name} must take (request, response) or (request, response, cassette)",
            )
        if interaction is None:
            return None
        if not isinstance(interaction, (tuple, list)) or len(interaction) != 2:
            # Hooks of untyped code can return anything.
            name = getattr(hook, "__qualname__", repr(hook))  # type: ignore[unreachable]
            raise TypeError(
                f"Interaction hook {name} must return (request, response) or None, "
                f"not {type(interaction).__name__}",
            )
        request, response = interaction
    return request, response


def _identity(value: _R) -> _R:
    return value


def _cassette_args(config: CassetteConfig) -> CassetteArgs:
    """The arguments of the cassette in config: all but its path and the decorator's options."""
    args = config.copy()
    args.pop("path", None)
    args.pop("path_transformer", None)
    args.pop("func_path_generator", None)
    args.pop("record_on_exception", None)
    return args


class InjectingCassetteContextDecorator(Protocol):
    """What ``use_cassette(inject_cassette=True)`` returns: as a decorator, it passes the
    cassette to the function as its first argument."""

    def __enter__(self) -> Cassette: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def __call__(self, function: Callable[Concatenate[Cassette, _P], _R]) -> Callable[_P, _R]: ...
