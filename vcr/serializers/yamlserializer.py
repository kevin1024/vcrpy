from io import BytesIO

import yaml

# Use the libYAML versions if possible
try:
    from yaml import CDumper as Dumper
    from yaml import CSafeLoader as _BaseLoader
except ImportError:
    from yaml import Dumper
    from yaml import SafeLoader as _BaseLoader


class _CassetteLoader(_BaseLoader):
    """A safe YAML loader for cassettes.

    It refuses the dangerous ``!!python/object``/``!!python/object/apply``/
    ``!!python/object/new``/``!!python/module``/``!!python/name`` tags that the
    full loader would execute (CVE-class: arbitrary code execution via
    untrusted cassette files), while still constructing the handful of benign
    Python-specific tags that vcrpy cassettes legitimately contain: plain
    strings, tuples, and serialized ``BytesIO`` request bodies. This keeps
    existing cassettes loadable.

    Note the ``BytesIO`` constructor is bound to the *exact* tag and rebuilds
    the buffer from its (safely constructed) byte content only. It never
    invokes PyYAML's generic object machinery, so it cannot be used to
    instantiate an arbitrary class.
    """


def _construct_python_str(loader, node):
    return loader.construct_scalar(node)


def _construct_python_tuple(loader, node):
    return tuple(loader.construct_sequence(node))


def _construct_bytesio(loader, node):
    # Older cassettes serialized file-like request bodies as a pickled
    # ``_io.BytesIO`` (``!!python/object/new:_io.BytesIO`` with a ``state``
    # tuple whose first element is the buffer content). Rebuild it from that
    # content only.
    mapping = loader.construct_mapping(node, deep=True)
    state = mapping.get("state") or (b"",)
    data = state[0] if state else b""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return BytesIO(data or b"")


def _construct_iter(loader, node):
    # Iterator request bodies were serialized as
    # ``!!python/object/apply:builtins.iter`` with ``args`` holding the
    # underlying sequence. Rebuild an iterator over that (safely constructed)
    # sequence; the hardcoded ``iter`` is the only callable ever invoked.
    mapping = loader.construct_mapping(node, deep=True)
    args = mapping.get("args") or ([],)
    return iter(args[0] if args else [])


_CassetteLoader.add_constructor("tag:yaml.org,2002:python/str", _construct_python_str)
_CassetteLoader.add_constructor("tag:yaml.org,2002:python/unicode", _construct_python_str)
_CassetteLoader.add_constructor("tag:yaml.org,2002:python/tuple", _construct_python_tuple)
_CassetteLoader.add_constructor("tag:yaml.org,2002:python/object/new:_io.BytesIO", _construct_bytesio)
_CassetteLoader.add_constructor("tag:yaml.org,2002:python/object/apply:builtins.iter", _construct_iter)


def deserialize(cassette_string):
    return yaml.load(cassette_string, Loader=_CassetteLoader)


def serialize(cassette_dict):
    return yaml.dump(cassette_dict, Dumper=Dumper)
