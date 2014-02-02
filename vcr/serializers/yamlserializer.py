import sys
import yaml
from . import compat

# Use the libYAML versions if possible
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

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

def _restore_frozenset():
    """
    Restore __builtin__.frozenset for cassettes serialized in python2 but 
    deserialized in python3 and builtins.frozenset for cassettes serialized
    in python3 and deserialized in python2
    """

    if '__builtin__' not in sys.modules:
        import builtins
        sys.modules['__builtin__'] = builtins

    if 'builtins' not in sys.modules:
        sys.modules['builtins'] = sys.modules['__builtin__']

def deserialize(cassette_string):
    _restore_frozenset()
    data = yaml.load(cassette_string, Loader=Loader)
    requests = [r['request'] for r in data]
    responses = [r['response'] for r in data]
    responses = [compat.convert_to_bytes(r['response']) for r in data]
    return requests, responses


def serialize(cassette_dict):
    data = ([{
        'request': request,
        'response': response,
    } for request, response in zip(
        cassette_dict['requests'],
        [compat.convert_to_unicode(r) for r in cassette_dict['responses']],
    )])
    return yaml.dump(data, Dumper=Dumper)
