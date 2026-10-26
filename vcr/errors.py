import os
import textwrap
from collections import Counter

from .util import read_body

DOCS = "https://vcrpy.readthedocs.io/en/latest/"
RECORD_MODES_DOCS = DOCS + "usage.html#record-modes"
PLAYBACK_REPEATS_DOCS = DOCS + "advanced.html#playback-repeats"
REQUEST_MATCHING_DOCS = DOCS + "configuration.html#request-matching"
IGNORE_REQUESTS_DOCS = DOCS + "advanced.html#ignore-requests"

# Keep the message readable when a cassette holds many similar requests.
MAX_SHOWN_SIMILAR_REQUESTS = 3
MAX_BODY_PREVIEW = 300


class CannotOverwriteExistingCassetteException(Exception):
    """Raised when a request isn't in the cassette and the record mode doesn't allow recording it.

    Besides ``cassette`` and ``failed_request``, it has:

    - ``reason``: why the request couldn't be handled, one of ``"cassette_not_found"``,
      ``"already_played"``, ``"no_match"`` and ``"nothing_similar"``.
    - ``similar_requests``: the recorded requests closest to ``failed_request``, as
      ``(request, succeeded_matchers, failed_matchers)`` tuples, where ``failed_matchers``
      is a list of ``(matcher_name, message)`` tuples.
    """

    def __init__(self, *args, **kwargs):
        self.cassette = kwargs["cassette"]
        self.failed_request = kwargs["failed_request"]
        self.similar_requests = self.cassette.find_requests_with_most_matches(self.failed_request)
        self.reason = _reason(self.cassette, self.similar_requests)
        super().__init__(_message(self.cassette, self.failed_request, self.similar_requests, self.reason))

    @staticmethod
    def _get_message(cassette, failed_request):
        """Get the final message related to the exception"""
        similar_requests = cassette.find_requests_with_most_matches(failed_request)
        return _message(cassette, failed_request, similar_requests, _reason(cassette, similar_requests))


class MissingMetadataError(CannotOverwriteExistingCassetteException):
    """Raised by ``Cassette.get_metadata`` for a key the cassette doesn't have,
    when the record mode doesn't allow adding it.

    It has the ``cassette`` and the missing ``key``. Its ``reason`` is
    ``"missing_metadata"``, and it has no ``failed_request`` or ``similar_requests``.
    """

    def __init__(self, *args, **kwargs):
        self.cassette = kwargs["cassette"]
        self.key = kwargs["key"]
        self.failed_request = None
        self.similar_requests = []
        self.reason = "missing_metadata"
        record_mode = getattr(self.cassette.record_mode, "value", self.cassette.record_mode)
        Exception.__init__(
            self,
            f"Can't add metadata {self.key!r} to cassette {self.cassette._path}: the cassette "
            f"doesn't have it, and record_mode {record_mode!r} doesn't allow changing it. Re-record "
            f"the cassette to store it, e.g. by deleting it, or use record_mode 'new_episodes'. "
            f"See {RECORD_MODES_DOCS}",
        )


class UnhandledHTTPRequestError(KeyError):
    """Raised when a cassette does not contain the request we want."""


def _reason(cassette, similar_requests):
    if not cassette.rewound and not len(cassette):
        return "cassette_not_found"
    if similar_requests and not similar_requests[0][2]:
        return "already_played"
    if similar_requests:
        return "no_match"
    return "nothing_similar"


def _message(cassette, request, similar_requests, reason):
    record_mode = getattr(cassette.record_mode, "value", cassette.record_mode)
    matcher_names = [getattr(matcher, "__name__", repr(matcher)) for matcher in cassette._match_on]

    lines = [_headline(cassette, similar_requests, reason, record_mode), ""]
    lines += [f"  {line}" for line in _describe_request(request, matcher_names)]
    lines += [
        "",
        f"Cassette: {cassette._path}",
        f"  record_mode: {record_mode}",
        f"  match_on: {', '.join(matcher_names)}",
        f"  interactions: {len(cassette)} recorded, {len(cassette.play_counts)} played",
    ]
    if reason == "no_match":
        lines += ["", *_describe_similar_requests(similar_requests)]

    suggestions = _suggestions(reason, record_mode)
    lines += ["", "How to fix:"]
    for number, (text, _link) in enumerate(suggestions, start=1):
        text = f"{text} [{number}]." if _link else text
        lines.append(textwrap.fill(text, width=80, initial_indent="  * ", subsequent_indent="    "))
    links = [link for _text, link in suggestions if link]
    if links:
        lines.append("")
        lines += [f"[{number}] {link}" for number, (_text, link) in enumerate(suggestions, start=1) if link]
    return "\n".join(lines)


def _headline(cassette, similar_requests, reason, record_mode):
    if reason == "cassette_not_found":
        problem = (
            "the cassette file couldn't be loaded"
            if _exists(cassette._path)
            else "the cassette doesn't exist"
        )
        return (
            f"Can't play back this request: {problem}, "
            f"and record_mode '{record_mode}' doesn't record new ones."
        )

    if record_mode == "none":
        not_recorded = "record_mode 'none' doesn't record new requests."
    else:
        not_recorded = f"record_mode '{record_mode}' doesn't record new requests into an existing cassette."

    if reason == "already_played":
        count = sum(1 for _request, _succeeded, failed in similar_requests if not failed)
        if count == 1:
            problem = "it matches 1 recorded interaction, but that has already been played back"
        else:
            problem = f"it matches {count} recorded interactions, but they have all been played back"
    elif reason == "no_match":
        differing = _join_names(name for name, _message in similar_requests[0][2])
        problem = f"no recorded interaction matches it (the closest differ in {differing})"
    else:
        problem = "the cassette has nothing similar to it"
    return f"Can't play back this request: {problem}.\n{not_recorded}"


def _describe_request(request, matcher_names):
    method, uri = getattr(request, "method", None), getattr(request, "uri", None)
    if method is None or uri is None:
        return [repr(request)]
    lines = [f"{method} {uri}"]
    if {"body", "raw_body"} & set(matcher_names):
        body = read_body(request)
        if body:
            lines.append(f"body: {_preview(body)}")
    return lines


def _preview(body):
    if isinstance(body, (bytes, bytearray)):
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            return f"<{len(body)} bytes of binary data>"
    else:
        text = str(body)
    if len(text) <= MAX_BODY_PREVIEW:
        return text
    return f"{text[:MAX_BODY_PREVIEW]}… ({len(text)} characters)"


def _describe_similar_requests(similar_requests):
    shown = similar_requests[:MAX_SHOWN_SIMILAR_REQUESTS]
    lines = ["Closest recorded requests:"]
    for number, (request, _succeeded, failed) in enumerate(shown, start=1):
        lines.append(f"  {number}. {_describe_request(request, [])[0]}")
        for name, message in failed:
            message = (message or "").strip()
            if not message or "\n" in message:
                lines.append(f"     {name} differs{':' if message else ''}")
                lines += [f"       {line}" for line in message.splitlines()]
            else:
                lines.append(f"     {name} differs: {message}")

    rest = similar_requests[MAX_SHOWN_SIMILAR_REQUESTS:]
    if rest:
        groups = Counter(tuple(name for name, _message in failed) for _request, _succeeded, failed in rest)
        if len(groups) == 1:
            ((names, count),) = groups.items()
            lines.append(f"  …and {count} more that also differ in {_join_names(names)}.")
        else:
            lines.append(f"  …and {len(rest)} more:")
            lines += [f"     {count} differ in {_join_names(names)}" for names, count in groups.most_common()]
    return lines


def _suggestions(reason, record_mode):
    record_it = (
        "record_mode='new_episodes' to add it to the cassette, or record_mode='all' with "
        "drop_unused_requests=True to re-record the cassette from scratch"
    )
    if reason == "cassette_not_found":
        return [
            (
                (
                    "Record the cassette first: run with record_mode='once' (the default) or "
                    "'new_episodes' to create it"
                ),
                RECORD_MODES_DOCS,
            ),
            ("If you expected the cassette to exist, check its path and cassette_library_dir", None),
        ]
    if reason == "already_played":
        return [
            (
                (
                    "If it's fine for this request to get the same response each time, set "
                    "allow_playback_repeats=True"
                ),
                PLAYBACK_REPEATS_DOCS,
            ),
            (
                "Otherwise record the extra request: run once with record_mode='new_episodes'",
                RECORD_MODES_DOCS,
            ),
        ]
    if reason == "no_match":
        return [
            (
                f"If the request changed on purpose, record it again: run once with {record_it}",
                RECORD_MODES_DOCS,
            ),
            (
                (
                    "If the difference changes on every run (a timestamp, a random ID), make matching "
                    "ignore it: loosen match_on, or normalize the request with before_record_request"
                ),
                REQUEST_MATCHING_DOCS,
            ),
        ]
    return [
        (f"To record this request, run once with {record_it}", RECORD_MODES_DOCS),
        (
            "If this request shouldn't be recorded at all, skip it with ignore_hosts or ignore_localhost",
            IGNORE_REQUESTS_DOCS,
        ),
    ]


def _join_names(names):
    names = list(names)
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"


def _exists(path):
    try:
        return os.path.exists(path)
    except (TypeError, ValueError):
        return False
