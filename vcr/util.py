import types
from collections.abc import Mapping, MutableMapping


# Shamelessly stolen from https://github.com/kennethreitz/requests/blob/master/requests/structures.py
class CaseInsensitiveDict(MutableMapping):
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

    def __init__(self, data=None, **kwargs):
        self._store = {}
        if data is None:
            data = {}
        self.update(data, **kwargs)

    def __setitem__(self, key, value):
        # Use the lowercased key for lookups, but store the actual
        # key alongside the value.
        self._store[key.lower()] = (key, value)

    def __getitem__(self, key):
        return self._store[key.lower()][1]

    def __delitem__(self, key):
        del self._store[key.lower()]

    def __iter__(self):
        return (casedkey for casedkey, mappedvalue in self._store.values())

    def __len__(self):
        return len(self._store)

    def lower_items(self):
        """Like iteritems(), but with all lowercase keys."""
        return ((lowerkey, keyval[1]) for (lowerkey, keyval) in self._store.items())

    def __eq__(self, other):
        if isinstance(other, Mapping):
            other = CaseInsensitiveDict(other)
        else:
            return NotImplemented
        # Compare insensitively
        return dict(self.lower_items()) == dict(other.lower_items())

    # Copy is required
    def copy(self):
        return CaseInsensitiveDict(self._store.values())

    def __repr__(self):
        return str(dict(self.items()))


def partition_dict(predicate, dictionary):
    true_dict = {}
    false_dict = {}
    for key, value in dictionary.items():
        this_dict = true_dict if predicate(key, value) else false_dict
        this_dict[key] = value
    return true_dict, false_dict


def compose(*functions):
    def composed(incoming):
        res = incoming
        for function in reversed(functions):
            if function:
                res = function(res)
        return res

    return composed


def _is_nonsequence_iterator(obj):
    return hasattr(obj, "__iter__") and not isinstance(
        obj,
        (bytearray, bytes, dict, list, str),
    )


def _is_async_iterator(obj):
    return hasattr(obj, "__aiter__")


def _join_body_chunks(chunks):
    """Join an iterable of body chunks into a single ``bytes`` object.

    Mirrors the chunk handling in :func:`read_body`: chunks may be
    ``bytes``/``bytearray``/``memoryview``, ``str`` (encoded as UTF-8),
    or ints (a bytes-like sequence of byte values).
    """
    chunks = list(chunks)
    if not chunks:
        return b""
    first = chunks[0]
    if isinstance(first, str):
        return "".join(chunks).encode("utf-8")
    if isinstance(first, (bytes, bytearray, memoryview)):
        return b"".join(bytes(chunk) for chunk in chunks)
    if isinstance(first, int):
        return bytes(chunks)
    raise ValueError(f"Body type {type(first)} not supported")


async def _buffer_async_body(body):
    """Drain an async iterator of body chunks into a single ``bytes``.

    Async generators (e.g. streaming file uploads) are single-use and
    cannot be copied, so the only way for a body to be both sent to the
    real server and recorded is to buffer it exactly once, up front.
    """
    chunks = [chunk async for chunk in body]
    return _join_body_chunks(chunks)


def read_body(request):
    if hasattr(request.body, "read"):
        return request.body.read()
    if _is_nonsequence_iterator(request.body):
        return _join_body_chunks(list(request.body))
    return request.body


def auto_decorate(decorator, predicate=lambda name, value: isinstance(value, types.FunctionType)):
    def maybe_decorate(attribute, value):
        if predicate(attribute, value):
            value = decorator(value)
        return value

    class DecorateAll(type):
        def __setattr__(cls, attribute, value):
            return super().__setattr__(attribute, maybe_decorate(attribute, value))

        def __new__(cls, name, bases, attributes_dict):
            new_attributes_dict = {
                attribute: maybe_decorate(attribute, value) for attribute, value in attributes_dict.items()
            }
            return super().__new__(cls, name, bases, new_attributes_dict)

    return DecorateAll
