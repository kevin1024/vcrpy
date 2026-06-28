from io import BytesIO

import yaml

# Use the libYAML versions if possible
try:
    from yaml import CDumper as _BaseDumper
    from yaml import CSafeLoader as _BaseLoader
except ImportError:
    from yaml import Dumper as _BaseDumper
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


class _CassetteDumper(_BaseDumper):
    """A YAML dumper that refuses to emit what the cassette loader can't read.

    Serializing with PyYAML's full dumper happily turns any Python object into
    a ``!!python/object``/``!!python/object/new``/``!!python/name`` tag. The
    cassette loader, being a *safe* loader, refuses those tags unless a
    constructor has been registered for them. Left unchecked, recording such a
    cassette would succeed and then fail to load later with a confusing error
    (see issue #1007).

    This dumper closes that gap: if it is about to emit a Python-specific tag
    that the loader has no constructor for, it raises immediately so the
    cassette is never written. The check uses the loader's own constructor
    table, so any tag made loadable via :func:`register_constructor` is also
    made dumpable, keeping the two sides symmetric.
    """

    def represent_data(self, data):
        node = super().represent_data(data)
        tag = node.tag
        if (
            isinstance(tag, str)
            and tag.startswith("tag:yaml.org,2002:python/")
            and tag not in _CassetteLoader.yaml_constructors
        ):
            raise yaml.representer.RepresenterError(
                "vcr refused to save the cassette because it contains a Python "
                f"object the safe loader could not read back ({tag!r}). Keep "
                "custom Python objects out of the recorded request/response, or "
                "register a constructor for the tag with "
                "vcr.serializers.yamlserializer.register_constructor(tag, constructor).",
            )
        return node


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


def register_constructor(tag, constructor):
    """Teach the cassette loader how to build a custom YAML tag.

    The cassette loader is a *safe* loader: for security it refuses the
    ``!!python/object`` family of tags by default. If your cassettes
    legitimately contain a custom Python object, register a constructor for
    its tag so the loader can rebuild it instead of raising an error.
    """
    _CassetteLoader.add_constructor(tag, constructor)


def deserialize(cassette_string):
    return yaml.load(cassette_string, Loader=_CassetteLoader)


def serialize(cassette_dict):
    return yaml.dump(cassette_dict, Dumper=_CassetteDumper)
