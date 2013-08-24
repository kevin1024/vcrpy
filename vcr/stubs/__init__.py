'''Stubs for patching HTTP and HTTPS requests'''

from httplib import HTTPConnection, HTTPSConnection, HTTPMessage
from cStringIO import StringIO

from vcr.request import Request


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

        # We are skipping the header parsing (they have already been parsed
        # at this point) and directly  adding the headers to the header
        # container, so just pass an empty StringIO.
        self.msg = HTTPMessage(StringIO(''))

        for key, val in self.recorded_response['headers'].iteritems():
            self.msg.addheader(key, val)
            # msg.addheaders adds the headers to msg.dict, but not to
            # the msg.headers list representation of headers, so
            # I have to add it to both.
            self.msg.headers.append("{0}:{1}".format(key, val))

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
        '''Persist the request metadata in self._vcr_request'''
        self._vcr_request = Request(
            protocol=self._protocol,
            host=self.host,
            port=self.port,
            method=method,
            path=url,
            body=body,
            headers=headers or {}
        )

        # Check if we have a cassette set, and if we have a response saved.
        # If so, there's no need to keep processing and we can bail
        if self.cassette and self._vcr_request in self.cassette:
            return

        # Otherwise, we should submit the request
        self._baseclass.request(
            self, method, url, body=body, headers=headers or {})

    def getresponse(self, _=False):
        '''Retrieve a the response'''
        # Check to see if the cassette has a response for this request. If so,
        # then return it
        if self._vcr_request in self.cassette:
            response = self.cassette.response_of(self._vcr_request)
            # Alert the cassette to the fact that we've served another
            # response for the provided requests
            self.cassette.mark_played(self._vcr_request)
            return VCRHTTPResponse(response)
        else:
            # Otherwise, we made an actual request, and should return the
            # response we got from the actual connection
            response = HTTPConnection.getresponse(self)
            response = {
                'status': {
                    'code': response.status,
                    'message': response.reason
                },
                'headers': dict(response.getheaders()),
                'body': {'string': response.read()},
            }
            self.cassette.append(self._vcr_request, response)
        return VCRHTTPResponse(response)


class VCRHTTPConnection(VCRConnectionMixin, HTTPConnection):
    '''A Mocked class for HTTP requests'''
    # Can't use super since this is an old-style class
    _baseclass = HTTPConnection
    _protocol = 'http'

    def __init__(self, *args, **kwargs):
        HTTPConnection.__init__(self, *args, **kwargs)


class VCRHTTPSConnection(VCRConnectionMixin, HTTPSConnection):
    '''A Mocked class for HTTPS requests'''
    _baseclass = HTTPSConnection
    _protocol = 'https'

    def __init__(self, *args, **kwargs):
        '''I overrode the init and copied a lot of the code from the parent
        class because HTTPConnection when this happens has been replaced by
        VCRHTTPConnection,  but doing it here lets us use the original one.'''
        HTTPConnection.__init__(self, *args, **kwargs)
        self.key_file = kwargs.pop('key_file', None)
        self.cert_file = kwargs.pop('cert_file', None)
