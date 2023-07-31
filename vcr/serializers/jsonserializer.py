import json


def deserialize(cassette_string):
    return json.loads(cassette_string)


def serialize(cassette_dict):
    error_message = (
        "Does this HTTP interaction contain binary data? "
        "If so, use a different serializer (like the yaml serializer) "
        "for this request?"
    )

    try:
        return json.dumps(cassette_dict, indent=4) + "\n"
    except TypeError:
        raise TypeError(error_message) from None
