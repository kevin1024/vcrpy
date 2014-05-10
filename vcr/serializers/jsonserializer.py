try:
    import simplejson as json
except ImportError:
    import json


def deserialize(cassette_string):
    return json.loads(cassette_string)


def serialize(cassette_dict):
    try:
        return json.dumps(cassette_dict, indent=4)
    except UnicodeDecodeError:
        raise UnicodeDecodeError(
            "Error serializing cassette to JSON. ",
            "Does this HTTP interaction contain binary data? ",
            "If so, use a different serializer (like the yaml serializer) ",
            "for this request"
        )
