class CannotOverwriteExistingCassetteException(Exception):
    pass


class UnhandledHTTPRequestError(KeyError):
    '''
    Raised when a cassette does not c
    ontain the request we want
    '''
    pass
