from __future__ import annotations

import sys
import types
from collections.abc import Callable, Iterable, Iterator, Mapping, MutableMapping
from io import BytesIO
from typing import TYPE_CHECKING

if sys.version_info >= (3, 13):
    from typing import TypeVar
else:
    from typing_extensions import TypeVar

if TYPE_CHECKING:
    from .request import Request
    from .types import BodyChunk, FormFields, OneOrMany

_K = TypeVar("_K")
_T = TypeVar("_T")
_V = TypeVar("_V", default=object)


# Shamelessly stolen from https://github.com/kennethreitz/requests/blob/master/requests/structures.py
class CaseInsensitiveDict(MutableMapping[str, _V]):
    """
    A case-insensitive ``dict``-like object.
    Implements all methods and operations of
    ``collections.abc.MutableMapping`` as well as dict's ``copy``. Also
    provides ``lower_items``.
    All keys are expected to be strings. The structure remembers the
    case of the last key to be set, and ``iter(instance)``,
    ``keys()``, ``items()``, ``iterkeys()``, and ``iteritems()``
    will contain case-sensitive keys. However, querying and contains
    testing is case insensitive::
        cid = CaseInsensitiveDict()
        cid['Accept'] = 'application/json'
        cid['aCCEPT'] == 'application/json'  # True
        list(cid) == ['Accept']  # True
    For example, ``headers['content-encoding']`` will return the
    value of a ``'Content-Encoding'`` response header, regardless
    of how the header name was originally stored.
    If the constructor, ``.update``, or equality comparison
    operations are given keys that have equal ``.lower()``s, the
    behavior is undefined.
    """

    def __init__(
        self,
        data: Mapping[str, _V] | Iterable[tuple[str, _V]] | None = None,
        **kwargs: _V,
    ) -> None:
        self._store: dict[str, tuple[str, _V]] = {}
        if data is None:
            data = {}
        self.update(data, **kwargs)

    def __setitem__(self, key: str, value: _V) -> None:
        # Use the lowercased key for lookups, but store the actual
        # key alongside the value.
        self._store[key.lower()] = (key, value)

    def __getitem__(self, key: str) -> _V:
        return self._store[key.lower()][1]

    def __delitem__(self, key: str) -> None:
        del self._store[key.lower()]

    def __iter__(self) -> Iterator[str]:
        return (casedkey for casedkey, mappedvalue in self._store.values())

    def __len__(self) -> int:
        return len(self._store)

    def lower_items(self) -> Iterator[tuple[str, _V]]:
        """Like iteritems(), but with all lowercase keys."""
        return ((lowerkey, keyval[1]) for (lowerkey, keyval) in self._store.items())

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mapping):
            other = CaseInsensitiveDict(other)
        else:
            return NotImplemented
        # Compare insensitively
        return dict(self.lower_items()) == dict(other.lower_items())

    # Copy is required
    def copy(self) -> CaseInsensitiveDict[_V]:
        return CaseInsensitiveDict(self._store.values())

    def __repr__(self) -> str:
        return str(dict(self.items()))


def partition_dict(
    predicate: Callable[[_K, _V], bool],
    dictionary: Mapping[_K, _V],
) -> tuple[dict[_K, _V], dict[_K, _V]]:
    true_dict: dict[_K, _V] = {}
    false_dict: dict[_K, _V] = {}
    for key, value in dictionary.items():
        this_dict = true_dict if predicate(key, value) else false_dict
        this_dict[key] = value
    return true_dict, false_dict


def compose(*functions: Callable[[_T], _T] | None) -> Callable[[_T], _T]:
    def composed(incoming: _T) -> _T:
        res = incoming
        for function in reversed(functions):
            if function:
                res = function(res)
        return res

    return composed


def as_list(items: OneOrMany[_T] | None) -> list[_T]:
    """A list of hooks from None, one hook, or several.

    Anything that isn't iterable is a single hook.
    """
    if items is None:
        return []
    if isinstance(items, Iterable):
        return list(items)
    return [items]


def _is_nonsequence_iterator(obj: object) -> bool:
    return hasattr(obj, "__iter__") and not isinstance(
        obj,
        (bytearray, bytes, dict, list, str),
    )


def _is_async_iterator(obj: object) -> bool:
    return hasattr(obj, "__aiter__")


def _join_body_chunks(chunks: Iterable[BodyChunk]) -> bytes:
    """Join an iterable of body chunks into a single ``bytes`` object.

    Mirrors the chunk handling in :func:`read_body`: chunks may be
    ``bytes``/``bytearray``/``memoryview``, ``str`` (encoded as UTF-8),
    or ints (a bytes-like sequence of byte values).
    """
    chunks = list(chunks)
    texts = [chunk for chunk in chunks if isinstance(chunk, str)]
    if len(texts) == len(chunks):
        return "".join(texts).encode("utf-8")
    buffers = [chunk for chunk in chunks if isinstance(chunk, (bytes, bytearray, memoryview))]
    if len(buffers) == len(chunks):
        return b"".join(bytes(chunk) for chunk in buffers)
    values = [chunk for chunk in chunks if isinstance(chunk, int)]
    if len(values) == len(chunks):
        return bytes(values)
    unsupported = [
        chunk for chunk in chunks if not isinstance(chunk, (str, bytes, bytearray, memoryview, int))
    ]
    if unsupported:
        raise ValueError(f"Body type {type(unsupported[0])} not supported")
    types_found = ", ".join(sorted({type(chunk).__name__ for chunk in chunks}))
    raise ValueError(f"Body chunks must all be str, all bytes-like or all ints, not a mix of {types_found}")


def read_body(request: Request) -> bytes | bytearray | FormFields | None:
    """The body of a request, with a file-like or iterator body read into bytes."""
    match request.body:
        case BytesIO() as file:
            return file.read()
        case Iterator() as chunks:
            return _join_body_chunks(chunks)
        case body:
            return body


def auto_decorate(
    decorator: Callable[[Callable[..., object]], Callable[..., object]],
    predicate: Callable[[str, object], bool] = lambda name, value: isinstance(value, types.FunctionType),
) -> type[type]:
    def maybe_decorate(attribute: str, value: object) -> object:
        if predicate(attribute, value) and callable(value):
            value = decorator(value)
        return value

    class DecorateAll(type):
        def __setattr__(cls, attribute: str, value: object) -> None:
            return super().__setattr__(attribute, maybe_decorate(attribute, value))

        def __new__(
            cls,
            name: str,
            bases: tuple[type, ...],
            attributes_dict: dict[str, object],
        ) -> DecorateAll:
            new_attributes_dict = {
                attribute: maybe_decorate(attribute, value) for attribute, value in attributes_dict.items()
            }
            return super().__new__(cls, name, bases, new_attributes_dict)

    return DecorateAll
