'''Stubs for patching HTTP and HTTPS requests'''

from httplib import HTTPConnection, HTTPSConnection, HTTPMessage
from cStringIO import StringIO


class VCRHTTPResponse(object):
    """
    Stub reponse class that gets returned instead of a HTTPResponse
    """
    def __init__(self, recorded_response):
        self.recorded_response = recorded_response
        self.reason = recorded_response['status']['message']
        self.status = recorded_response['status']['code']
        self.version = None
        self._content = StringIO(self.recorded_response['body']['string'])

        self.msg = HTTPMessage(StringIO(''))
        for key, val in self.recorded_response['headers'].iteritems():
            self.msg.addheader(key, val)

        self.length = self.msg.getheader('content-length') or None

    def read(self, *args, **kwargs):
        # Note: I'm pretty much ignoring any chunking stuff because
        # I don't really understand what it is or how it works.
        return self._content.read(*args, **kwargs)

    def close(self):
        return True

    def isclosed(self):
        # Urllib3 seems to call this because it actually uses
        # the weird chunking support in httplib
        return True

    def getheaders(self):
        return self.recorded_response['headers'].iteritems()


class VCRConnectionMixin:
    # A reference to the cassette that's currently being patched in
    cassette = None

    def request(self, method, url, body=None, headers=None):
        '''Persist the request metadata in self._vcr'''
        self._request = {
            'host': self.host,
            'port': self.port,
            'method': method,
            'url': url,
            'body': body,
            'headers': headers or {},
        }
        # Check if we have a cassette set, and if we have a response saved.
        # If so, there's no need to keep processing and we can bail
        if self.cassette and self._request in self.cassette:
            return

        # Otherwise, we should submit the request
        self._baseclass.request(
            self, method, url, body=body, headers=headers or {})

    def getresponse(self, _=False):
        '''Retrieve a the response'''
        # Check to see if the cassette has a response for this request. If so,
        # then return it
        response = self.cassette.response(self._request)
        if response:
            # Alert the cassette to the fact that we've served another
            # response for the provided requests
            self.cassette.mark_played()
            return VCRHTTPResponse(response)

        # Otherwise, we made an actual request, and should return the response
        # we got from the actual connection
        response = HTTPConnection.getresponse(self)
        response = {
            'status': {'code': response.status, 'message': response.reason},
            'headers': dict(response.getheaders()),
            'body': {'string': response.read()},
        }
        self.cassette.append(self._request, response)
        return VCRHTTPResponse(response)


class VCRHTTPConnection(VCRConnectionMixin, HTTPConnection):
    '''A Mocked class for HTTP requests'''
    # Can't use super since this is an old-style class
    _baseclass = HTTPConnection

    def __init__(self, *args, **kwargs):
        HTTPConnection.__init__(self, *args, **kwargs)


class VCRHTTPSConnection(VCRConnectionMixin, HTTPSConnection):
    '''A Mocked class for HTTPS requests'''
    _baseclass = HTTPSConnection

    def __init__(self, *args, **kwargs):
        '''I overrode the init and copied a lot of the code from the parent
        class because HTTPConnection when this happens has been replaced by
        VCRHTTPConnection,  but doing it here lets us use the original one.'''
        HTTPConnection.__init__(self, *args, **kwargs)
        self.key_file = kwargs.pop('key_file', None)
        self.cert_file = kwargs.pop('cert_file', None)
