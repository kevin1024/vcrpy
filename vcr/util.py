import collections
import types

import six


class DictDecorator(collections.MutableMapping):

    def __init__(self, data=None, store_type=dict):
        self._store_type = store_type
        self._store = self._store_type()
        if data is None:
            data = {}
        self.update(data)

    def __setitem__(self, key, value):
        self._store[key] = value

    def __getitem__(self, key):
        return self._store[key]

    def __delitem__(self, key):
        del self._store[key]

    def __iter__(self):
        return iter(self._store)

    def __len__(self):
        return len(self._store)

    def __getattr__(self, attr):
        return getattr(self._store, attr)

    def __contains__(self, key):
        return key in self._store

    def setdefault(self, key, default=None):
        return self._store.setdefault(key, default)

    def copy(self):
        return type(self)(data=self._store, store_type=self._store_type)

    @property
    def underlying_store(self):
        return (self._store.underlying_store
                if hasattr(self._store, 'underlying_store')
                else self._store)


KVPair = collections.namedtuple('KVPair', ['key', 'value'])


# Adapted from:
# https://github.com/kennethreitz/requests/blob/master/requests/structures.py
class CaseInsensitiveDict(DictDecorator):

    def __setitem__(self, key, value):
        # Use the lowercased key for lookups, but store the actual
        # key alongside the value.
        self._store[key.lower()] = KVPair(key, value)

    def __getitem__(self, key):
        return self._store[key.lower()]

    def __delitem__(self, key):
        del self._store[key.lower()]

    def __len__(self):
        return len(self._store)

    def __contains__(self, key):
        return key.lower() in self._store

    def __repr__(self):
        return str(dict(self.items()))


class MultiValueDict(DictDecorator):

    _no_set_iterables = six.string_types + (KVPair,)

    def __setitem__(self, key, value):
        if (not isinstance(value, self._no_set_iterables) and
                isinstance(value, collections.Iterable)):
            self._store[key] = collections.deque(value)
            return
        if key not in self._store:
            self._store[key] = collections.deque()
        self._store[key].appendleft(value)


class HeadersDict(CaseInsensitiveDict):
    """A dictionary object that is adapted to the specific case of
    representing HTTP requests.

    The HTTP spec has a strange quirk where it allows the submission
    of a single header twice. For this reason, HeadersDict instances
    map each case insensitive header string to a list of values that
    were provided for that header. However, since httplib is incapable
    of sending the same header twice, HeadersDict provides the
    property `single_valued`, which returns a version of the headers
    dict where each header key is mapped to the single value at index
    0 for that key in the HeadersDict store.
    """

    def __init__(self, data=None, store_type=None):
        super(HeadersDict, self).__init__(data, store_type=MultiValueDict)

    @property
    def single_valued(self):
        return dict(
            key_value_pairs[0]
            for key_value_pairs in self.values()
        )

    @property
    def serialize(self):
        return dict(
            (lower_key, [(key, value) for key, value in value_pairs])
            for lower_key, value_pairs in self.items()
        )


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


def read_body(request):
    if hasattr(request.body, 'read'):
        return request.body.read()
    return request.body


def auto_decorate(
    decorator,
    predicate=lambda name, value: isinstance(value, types.FunctionType)
):
    def maybe_decorate(attribute, value):
        if predicate(attribute, value):
            value = decorator(value)
        return value

    class DecorateAll(type):

        def __setattr__(cls, attribute, value):
            return super(DecorateAll, cls).__setattr__(
                attribute, maybe_decorate(attribute, value)
            )

        def __new__(cls, name, bases, attributes_dict):
            new_attributes_dict = dict(
                (attribute, maybe_decorate(attribute, value))
                for attribute, value in attributes_dict.items()
            )
            return super(DecorateAll, cls).__new__(
                cls, name, bases, new_attributes_dict
            )
    return DecorateAll
