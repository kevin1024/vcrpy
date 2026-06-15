from enum import Enum


class RecordMode(str, Enum):
    """
    Configures when VCR will record to the cassette.

    Can be declared by either using the enumerated value (`vcr.mode.ONCE`)
    or by simply using the defined string (`once`).

    `ALL`: Every request is recorded.
    `ANY`: ?
    `NEW_EPISODES`: Any request not found in the cassette is recorded.
    `NONE`: No requests are recorded.
    `ONCE`:  First set of requests is recorded, all others are replayed.
    Attempting to add a new episode fails.
    """

    ALL = "all"
    ANY = "any"
    NEW_EPISODES = "new_episodes"
    NONE = "none"
    ONCE = "once"


def validate_record_mode(record_mode):
    """Coerce and validate a user-supplied record mode.

    Accepts either a ``RecordMode`` or one of its string values and returns the
    corresponding ``RecordMode``. Raises ``ValueError`` with a helpful message
    for anything else, so a misspelled mode fails loudly instead of silently
    behaving like ``new_episodes``.
    """
    try:
        return RecordMode(record_mode)
    except ValueError:
        valid_modes = ", ".join(repr(mode.value) for mode in RecordMode)
        raise ValueError(
            f"{record_mode!r} is not a valid record_mode. Valid modes are: {valid_modes}.",
        ) from None
