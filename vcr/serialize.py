import yaml

from vcr.request import Request
from vcr.serializers import compat

# version 1 cassettes started with VCR 1.0.x.
# Before 1.0.x, there was no versioning.
CASSETTE_FORMAT_VERSION = 1

"""
Just a general note on the serialization philosophy here:
I prefer cassettes to be human-readable if possible.  Yaml serializes
bytestrings to !!binary, which isn't readable, so I would like to serialize to
strings and from strings, which yaml will encode as utf-8 automatically.
All the internal HTTP stuff expects bytestrings, so this whole serialization
process feels backwards.

Serializing: bytestring -> string (yaml persists to utf-8)
Deserializing: string (yaml converts from utf-8) -> bytestring
"""


def _looks_like_an_old_cassette(data):
    return isinstance(data, list) and len(data) and "request" in data[0]


def _warn_about_old_cassette_format():
    raise ValueError(
        "Your cassette files were generated in an older version "
        "of VCR. Delete your cassettes or run the migration script."
        "See http://git.io/mHhLBg for more details.",
    )


def deserialize(cassette_string, serializer):
    try:
        data = serializer.deserialize(cassette_string)
    except ImportError:
        # Old cassettes used to use yaml object thingy
        _warn_about_old_cassette_format()
    except yaml.constructor.ConstructorError as e:
        # The cassette contains a YAML tag that VCR's safe loader does not
        # support (e.g. a custom Python object type recorded by an older VCR
        # version, or a non-standard type in the request/response body).
        # Raise a descriptive error rather than the misleading "older version"
        # message; still mention the migration script since old cassettes with
        # Python object tags are the most common cause.
        raise ValueError(
            f"There was a problem loading the cassette: {e}. "
            "If this is an old cassette, delete it and re-record, or "
            "run the migration script. "
            "See http://git.io/mHhLBg for more details."
        ) from e
    if _looks_like_an_old_cassette(data):
        _warn_about_old_cassette_format()

    requests = [Request._from_dict(r["request"]) for r in data["interactions"]]
    responses = [compat.convert_to_bytes(r["response"]) for r in data["interactions"]]
    return requests, responses


def serialize(cassette_dict, serializer):
    interactions = [
        {
            "request": compat.convert_to_unicode(request._to_dict()),
            "response": compat.convert_to_unicode(response),
        }
        for request, response in zip(cassette_dict["requests"], cassette_dict["responses"], strict=False)
    ]
    data = {"version": CASSETTE_FORMAT_VERSION, "interactions": interactions}
    return serializer.serialize(data)
