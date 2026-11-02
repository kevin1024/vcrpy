from __future__ import annotations

import logging
import sys
import warnings
from collections.abc import Iterable
from contextlib import suppress
from io import BytesIO
from typing import TYPE_CHECKING, Protocol, Self, runtime_checkable
from urllib.parse import ParseResult, parse_qsl, urlparse

from .util import CaseInsensitiveDict, _is_nonsequence_iterator, _join_body_chunks

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

if sys.version_info >= (3, 13):
    from typing import TypeVar
else:
    from typing_extensions import TypeVar

if TYPE_CHECKING:
    from .types import (
        BodyChunk,
        FormFields,
        HeadersIn,
        HeaderValue,
        RequestBody,
        RequestBodyIn,
        RequestDict,
        SerializedRequest,
    )

log: logging.Logger = logging.getLogger(__name__)

_K = TypeVar("_K")
_V_co = TypeVar("_V_co", covariant=True, default=object)


@runtime_checkable
class SupportsKeysAndGetItem(Protocol[_K, _V_co]):
    """What ``dict.update`` takes besides pairs: a mapping, or anything with ``keys`` and ``[]``."""

    def keys(self) -> Iterable[_K]: ...

    def __getitem__(self, key: _K, /) -> _V_co: ...


@runtime_checkable
class Readable(Protocol):
    """A file-like request body. It's read when it's given to a request, and rewound if it can seek."""

    def read(self) -> bytes | str: ...


@runtime_checkable
class _Seekable(Protocol):
    def tell(self) -> int: ...

    def seek(self, offset: int, /) -> object: ...


class _FileBody:
    """The content of a file-like body, which ``Request.body`` returns as a ``BytesIO``."""

    def __init__(self, content: bytes) -> None:
        self.content = content


class _IterableBody:
    """The chunks of an iterable body, which ``Request.body`` returns as an iterator."""

    def __init__(self, chunks: list[BodyChunk]) -> None:
        self.chunks = chunks


class _OpaqueBody:
    """A body of a kind vcrpy doesn't know, like aiohttp's ``FormData``, kept as it is.

    Typed callers can't pass one, but HTTP libraries can. It can't be recorded.
    """

    def __init__(self, value: object) -> None:
        self.value = value


def _read_file(body: Readable) -> bytes:
    position = body.tell() if isinstance(body, _Seekable) else None
    content = body.read()
    if position is not None and isinstance(body, _Seekable):
        body.seek(position)
    return content.encode("utf-8") if isinstance(content, str) else content


class Request:
    """
    VCR's representation of a request.
    """

    def __init__(self, method: str, uri: str, body: RequestBodyIn, headers: HeadersIn) -> None:
        self.method = method
        self.uri = uri
        self.body = body
        self.headers = headers
        log.debug("Invoking Request %s", self.uri)

    @property
    def uri(self) -> str:
        return self._uri

    @uri.setter
    def uri(self, uri: str) -> None:
        self._uri = uri
        self.parsed_uri: ParseResult = urlparse(uri)

    @property
    def headers(self) -> HeadersDict:
        return self._headers

    @headers.setter
    def headers(self, value: HeadersIn) -> None:
        if not isinstance(value, HeadersDict):
            value = HeadersDict(value)
        self._headers = value

    @property
    def body(self) -> RequestBody:
        """The body, with a str encoded as UTF-8.

        A file-like body is returned as a new ``BytesIO``, and an iterable body as a new
        iterator, each time, so the body can be read again. Assigning a body converts it
        the same way, so ``request.body = request.body`` changes nothing.
        """
        match self._body:
            case _FileBody(content=content):
                return BytesIO(content)
            case _IterableBody(chunks=chunks):
                return iter(chunks)
            case _OpaqueBody(value=value):
                return value  # type: ignore[return-value]  # only HTTP libraries make these
            case body:
                return body

    @body.setter
    def body(self, value: RequestBodyIn) -> None:
        self._body: bytes | bytearray | FormFields | _FileBody | _IterableBody | _OpaqueBody | None
        match value:
            case str():
                self._body = value.encode("utf-8")
            case None | bytes() | bytearray():
                self._body = value
            case dict() | list():
                # Form fields, as aiohttp records them
                self._body = value
            case Readable():
                self._body = _FileBody(_read_file(value))
            case _ if _is_nonsequence_iterator(value):
                self._body = _IterableBody(list(value))
            case _:
                self._body = _OpaqueBody(value)

    @property
    def body_bytes(self) -> bytes | bytearray | FormFields | None:
        """The body materialized as a single ``bytes`` object (or ``None``).

        Used when forwarding to a real server so ``http.client`` sets a
        ``Content-Length`` instead of chunk-encoding a file-like/iterator body
        (which some servers, including the wsgiref-based test server, reject).
        """
        match self._body:
            case _FileBody(content=content):
                return content
            case _IterableBody(chunks=chunks):
                return _join_body_chunks(chunks)
            case _OpaqueBody(value=value):
                return value  # type: ignore[return-value]  # only HTTP libraries make these
            case body:
                return body

    def add_header(self, key: str, value: str | bytes) -> None:
        warnings.warn(
            "Request.add_header is deprecated. Please assign to request.headers instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.headers[key] = value

    @property
    def scheme(self) -> str:
        return self.parsed_uri.scheme

    @property
    def host(self) -> str | None:
        return self.parsed_uri.hostname

    @property
    def port(self) -> int | None:
        port = self.parsed_uri.port
        if port is None:
            with suppress(KeyError):
                port = {"https": 443, "http": 80}[self.parsed_uri.scheme]

        return port

    @property
    def path(self) -> str:
        return self.parsed_uri.path

    @property
    def query(self) -> list[tuple[str, str]]:
        q = self.parsed_uri.query
        return sorted(parse_qsl(q))

    # alias for backwards compatibility
    @property
    def url(self) -> str:
        return self.uri

    # alias for backwards compatibility
    @property
    def protocol(self) -> str:
        return self.scheme

    @override
    def __str__(self) -> str:
        return f"<Request ({self.method}) {self.uri}>"

    @override
    def __repr__(self) -> str:
        return self.__str__()

    def _to_dict(self) -> RequestDict:
        return {
            "method": self.method,
            "uri": self.uri,
            "body": self.body,
            "headers": {k: [v] for k, v in self.headers.items()},
        }

    @classmethod
    def _from_dict(cls, dct: RequestDict | SerializedRequest) -> Self:
        return cls(method=dct["method"], uri=dct["uri"], body=dct["body"], headers=dct["headers"])


class HeadersDict(CaseInsensitiveDict[str | bytes]):
    """
    There is a weird quirk in HTTP.  You can send the same header twice.  For
    this reason, headers are represented by a dict, with lists as the values.
    However, it appears that HTTPlib is completely incapable of sending the
    same header twice.  This puts me in a weird position: I want to be able to
    accurately represent HTTP headers in cassettes, but I don't want the extra
    step of always having to do [0] in the general case, i.e.
    request.headers['key'][0]

    In addition, some servers sometimes send the same header more than once,
    and httplib *can* deal with this situation.

    Furthermore, I wanted to keep the request and response cassette format as
    similar as possible.

    For this reason, in cassettes I keep a dict with lists as keys, but once
    deserialized into VCR, I keep them as plain, naked dicts.
    """

    def __init__(self, data: HeadersIn | None = None, **kwargs: HeaderValue) -> None:
        super().__init__()
        # Like dict.update, but through __setitem__, which keeps the first of several values.
        match data:
            case None:
                pass
            case SupportsKeysAndGetItem():
                for key in data.keys():  # noqa: SIM118 - it has keys(), but needn't be iterable
                    self[key] = data[key]
            case _:
                for key, value in data:
                    self[key] = value
        for key, value in kwargs.items():
            self[key] = value

    @override
    def __setitem__(self, key: str, value: HeaderValue) -> None:
        if isinstance(value, (tuple, list)):
            value = value[0]

        # Preserve the case from the first time this key was set.
        old = self._store.get(key.lower())
        if old:
            key = old[0]

        super().__setitem__(key, value)
