from __future__ import annotations

import sys
from collections.abc import Callable, Hashable, Iterable, Iterator, Mapping
from io import BytesIO
from typing import TYPE_CHECKING, ClassVar

import yaml

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

if TYPE_CHECKING:
    from ..types import SerializedCassette, Serializer

# Use the libYAML versions if possible. They have the same API, so type checkers see those.
if TYPE_CHECKING:
    from yaml import CDumper as _BaseDumper
    from yaml import CSafeLoader as _BaseLoader
else:
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


def _construct_python_str(loader: _CassetteLoader, node: yaml.ScalarNode) -> str:
    return loader.construct_scalar(node)


def _construct_python_tuple(loader: _CassetteLoader, node: yaml.SequenceNode) -> tuple[object, ...]:
    return tuple(loader.construct_sequence(node))


def _construct_bytesio(loader: _CassetteLoader, node: yaml.MappingNode) -> BytesIO:
    # Older cassettes serialized file-like request bodies as a pickled
    # ``_io.BytesIO`` (``!!python/object/new:_io.BytesIO`` with a ``state``
    # tuple whose first element is the buffer content). Rebuild it from that
    # content only.
    mapping: dict[Hashable, object] = loader.construct_mapping(node, deep=True)
    match mapping.get("state"):
        case [str() as text, *_]:
            return BytesIO(text.encode("utf-8"))
        case [bytes() as data, *_]:
            return BytesIO(data)
        case _:
            return BytesIO(b"")


def _construct_iter(loader: _CassetteLoader, node: yaml.MappingNode) -> Iterator[object]:
    # Iterator request bodies were serialized as
    # ``!!python/object/apply:builtins.iter`` with ``args`` holding the
    # underlying sequence. Rebuild an iterator over that (safely constructed)
    # sequence; the hardcoded ``iter`` is the only callable ever invoked.
    mapping: dict[Hashable, object] = loader.construct_mapping(node, deep=True)
    match mapping.get("args"):
        case [Iterable() as items, *_]:
            return iter(items)
        case _:
            return iter([])


_CassetteLoader.add_constructor("tag:yaml.org,2002:python/str", _construct_python_str)
_CassetteLoader.add_constructor("tag:yaml.org,2002:python/unicode", _construct_python_str)
_CassetteLoader.add_constructor("tag:yaml.org,2002:python/tuple", _construct_python_tuple)
_CassetteLoader.add_constructor("tag:yaml.org,2002:python/object/new:_io.BytesIO", _construct_bytesio)
_CassetteLoader.add_constructor("tag:yaml.org,2002:python/object/apply:builtins.iter", _construct_iter)


class _CassetteDumper(_BaseDumper):
    """A YAML dumper that refuses to emit what the cassette loader can't read.

    PyYAML's full dumper happily turns any Python object into a
    ``!!python/object*`` tag, but the safe cassette loader refuses those tags,
    so recording such a cassette would succeed and then fail to load on replay
    (#1007). Refuse at record time instead, before anything is written. The
    check uses the paired loader's constructor table, so any tag the loader
    can construct is also dumpable and the two sides stay symmetric.
    """

    loader_class: ClassVar[type[_CassetteLoader]] = _CassetteLoader

    @override
    def represent_data(self, data: object) -> yaml.Node:
        node = super().represent_data(data)
        tag = node.tag
        if (
            isinstance(tag, str)
            and tag.startswith("tag:yaml.org,2002:python/")
            and tag not in self.loader_class.yaml_constructors
        ):
            raise yaml.representer.RepresenterError(
                "Cassette not saved: the request or response contains a Python "
                f"object that the safe YAML loader would refuse to load back ({tag!r}). "
                "Keep custom Python objects out of recorded requests/responses, or "
                "register a serializer that supports this object on your VCR "
                "instance:\n\n"
                "    from vcr.serializers import yamlserializer\n\n"
                '    my_vcr.register_serializer("yaml", yamlserializer.with_custom_tags({\n'
                f"        {tag!r}: my_constructor,  # def my_constructor(loader, node): ...\n"
                "    }))\n\n"
                "See https://vcrpy.readthedocs.io/en/latest/advanced.html"
                "#cassettes-containing-custom-python-objects",
            )
        return node


def with_custom_tags(
    constructors: Mapping[str, Callable[[_CassetteLoader, yaml.Node], object]],
) -> Serializer:
    """Build a YAML serializer that can record and replay custom Python objects.

    ``constructors`` maps YAML tags to PyYAML constructor callables. The
    returned serializer's loader knows how to construct those tags, and its
    dumper therefore allows saving them; everything else stays as locked down
    as the default serializer. Register the result on a VCR instance::

        my_vcr.register_serializer("yaml", yamlserializer.with_custom_tags({
            "tag:yaml.org,2002:python/object/new:myapp.CustomHeader":
                lambda loader, node: CustomHeader(loader.construct_sequence(node)[0]),
        }))
    """

    class _CustomTagCassetteLoader(_CassetteLoader):
        pass

    for tag, constructor in constructors.items():
        _CustomTagCassetteLoader.add_constructor(tag, constructor)

    class _CustomTagCassetteDumper(_CassetteDumper):
        loader_class = _CustomTagCassetteLoader

    loader, dumper = _CustomTagCassetteLoader, _CustomTagCassetteDumper

    class _CustomTagSerializer:
        @staticmethod
        def deserialize(cassette_string: str) -> SerializedCassette:
            data: SerializedCassette = yaml.load(cassette_string, Loader=loader)
            return data

        @staticmethod
        def serialize(cassette_dict: SerializedCassette) -> str:
            text: str = yaml.dump(cassette_dict, Dumper=dumper)
            return text

    return _CustomTagSerializer()


def deserialize(cassette_string: str) -> SerializedCassette:
    data: SerializedCassette = yaml.load(cassette_string, Loader=_CassetteLoader)
    return data


def serialize(cassette_dict: SerializedCassette) -> str:
    text: str = yaml.dump(cassette_dict, Dumper=_CassetteDumper)
    return text
