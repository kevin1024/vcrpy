from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import SerializedCassette


def deserialize(cassette_string: str) -> SerializedCassette:
    data: SerializedCassette = json.loads(cassette_string)
    return data


def serialize(cassette_dict: SerializedCassette) -> str:
    error_message = (
        "Does this HTTP interaction contain binary data? "
        "If so, use a different serializer (like the yaml serializer) "
        "for this request?"
    )

    try:
        return json.dumps(cassette_dict, indent=4) + "\n"
    except TypeError:
        raise TypeError(error_message) from None
