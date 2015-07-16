import six


def convert_to_unicode(resp):
    resp = convert_body_to_unicode(resp)
    return resp


def convert_body_to_bytes(body):
    """
    If body is a text string, encode it to bytes (for python3 support)

    By default yaml serializes to utf-8 encoded bytestrings.
    When this cassette is loaded by python3, it's automatically decoded
    into unicode strings.  This makes sure that it stays a bytestring, since
    that's what all the internal httplib machinery is expecting.

    For more info on py3 yaml:
    http://pyyaml.org/wiki/PyYAMLDocumentation#Python3support
    """
    # Safe to assume valid UTF-8 here, since it comes from a YAML file.
    if isinstance(body, six.text_type):
        return body.encode('utf-8')
    return body


def convert_body_to_unicode(resp):
    """
    If the request body is bytes, decode it to a string (for python3 support)
    """
    try:
        if not isinstance(resp['body']['string'], six.text_type):
            resp['body']['string'] = resp['body']['string'].decode('utf-8')
    except (KeyError, TypeError, UnicodeDecodeError):
        # The thing we were converting either wasn't a dictionary or didn't
        # have the keys we were expecting.  Some of the tests just serialize
        # and deserialize a string.

        # Also, sometimes the thing actually is binary, so if you can't decode
        # it, just give up.
        pass
    return resp
