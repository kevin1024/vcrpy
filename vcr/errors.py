class CannotOverwriteExistingCassetteException(Exception):
    pass


class UnhandledHTTPRequestError(KeyError):
    """Raised when a cassette does not contain the request we want."""
    pass
