'''Stubs for patching HTTP and HTTPS requests'''

try:
    import http.client
except ImportError:
    pass
import six
from six.moves.http_client import (
    HTTPConnection,
    HTTPSConnection,
    HTTPMessage,
    HTTPResponse,
)
from six import BytesIO
from vcr.request import Request
from vcr.errors import CannotOverwriteExistingCassetteException
from . import compat


def parse_headers_backwards_compat(header_dict):
    """
    In vcr 0.6.0, I changed the cassettes to store
    headers as a list instead of a dict.  This method
    parses the old dictionary-style headers for
    backwards-compatability reasons.
    """
    msg = HTTPMessage(BytesIO(""))
    for key, val in header_dict.items():
        msg.addheader(key, val)
        msg.headers.append("{0}:{1}".format(key, val))
    return msg


def parse_headers(header_list):
    if isinstance(header_list, dict):
        return parse_headers_backwards_compat(header_list)
    headers = b"".join(header_list) + b"\r\n"
    return compat.get_httpmessage(headers)


class VCRHTTPResponse(HTTPResponse):
    """
    Stub reponse class that gets returned instead of a HTTPResponse
    """
    def __init__(self, recorded_response):
        self.recorded_response = recorded_response
        self.reason = recorded_response['status']['message']
        self.status = self.code = recorded_response['status']['code']
        self.version = None
        self._content = BytesIO(self.recorded_response['body']['string'])
        self._closed = False

        headers = self.recorded_response['headers']
        self.msg = parse_headers(headers)

        self.length = compat.get_header(self.msg, 'content-length') or None

    @property
    def closed(self):
        # in python3, I can't change the value of self.closed.  So I'
        # twiddling self._closed and using this property to shadow the real
        # self.closed from the superclas
        return self._closed

    def read(self, *args, **kwargs):
        return self._content.read(*args, **kwargs)

    def readline(self, *args, **kwargs):
        return self._content.readline(*args, **kwargs)

    def close(self):
        self._closed = True
        return True

    def getcode(self):
        return self.status

    def isclosed(self):
        return self.closed

    def info(self):
        return parse_headers(self.recorded_response['headers'])

    def getheaders(self):
        message = parse_headers(self.recorded_response['headers'])
        return compat.get_header_items(message)

    def getheader(self, header, default=None):
        headers = dict(((k, v) for k, v in self.getheaders()))
        return headers.get(header, default)


class VCRConnection:
    # A reference to the cassette that's currently being patched in
    cassette = None

    def request(self, method, url, body=None, headers=None):
        '''Persist the request metadata in self._vcr_request'''

        self._vcr_request = Request(
            protocol=self._protocol,
            host=self.real_connection.host,
            port=self.real_connection.port,
            method=method,
            path=url,
            body=body,
            headers=headers or {}
        )

        # Note: The request may not actually be finished at this point, so
        # I'm not sending the actual request until getresponse().  This
        # allows me to compare the entire length of the response to see if it
        # exists in the cassette.

    def putrequest(self, method, url, *args, **kwargs):
        """
        httplib gives you more than one way to do it.  This is a way
        to start building up a request.  Usually followed by a bunch
        of putheader() calls.
        """
        self._vcr_request = Request(
            protocol=self._protocol,
            host=self.real_connection.host,
            port=self.real_connection.port,
            method=method,
            path=url,
            body="",
            headers={}
        )

    def putheader(self, header, *values):
        for value in values:
            self._vcr_request.add_header(header, value)

    def send(self, data):
        '''
        This method is called after request(), to add additional data to the
        body of the request.  So if that happens, let's just append the data
        onto the most recent request in the cassette.
        '''
        self._vcr_request.body = (self._vcr_request.body or '') + data

    def close(self):
        # Note: the real connection will only close if it's open, so
        # no need to check that here.
        self.real_connection.close()

    def endheaders(self, *args, **kwargs):
        """
        Normally, this would atually send the request to the server.
        We are not sending the request until getting the response,
        so bypass this method for now.
        """
        pass

    def getresponse(self, _=False):
        '''Retrieve a the response'''
        # Check to see if the cassette has a response for this request. If so,
        # then return it
        if self._vcr_request in self.cassette and \
                self.cassette.record_mode != "all" and \
                self.cassette.rewound:
            response = self.cassette.play_response(self._vcr_request)
            return VCRHTTPResponse(response)
        else:
            if self.cassette.write_protected:
                raise CannotOverwriteExistingCassetteException(
                    "Can't overwrite existing cassette (%r) in "
                    "your current record mode (%r)."
                    % (self.cassette._path, self.cassette.record_mode)
                )

            # Otherwise, we should send the request, then get the response
            # and return it.

            self.real_connection.request(
                method=self._vcr_request.method,
                url=self._vcr_request.path,
                body=self._vcr_request.body,
                headers=dict(self._vcr_request.headers or {})
            )

            # get the response
            response = self.real_connection.getresponse()

            # put the response into the cassette
            response = {
                'status': {
                    'code': response.status,
                    'message': response.reason
                },
                'headers': compat.get_headers(response),
                'body': {'string': response.read()},
            }
            self.cassette.append(self._vcr_request, response)
        return VCRHTTPResponse(response)

    def set_debuglevel(self, *args, **kwargs):
        self.real_connection.set_debuglevel(*args, **kwargs)

    def connect(self, *args, **kwargs):
        """
        httplib2 uses this.  Connects to the server I'm assuming.

        Only pass to the baseclass if we don't have a recorded response
        and are not write-protected.
        """

        if hasattr(self, '_vcr_request') and \
                self._vcr_request in self.cassette and \
                self.cassette.record_mode != "all" and \
                self.cassette.rewound:
            # We already have a response we are going to play, don't
            # actually connect
            return

        if self.cassette.write_protected:
            # Cassette is write-protected, don't actually connect
            return

        return self.real_connection.connect(*args, **kwargs)

    def __init__(self, *args, **kwargs):
        # need to temporarily reset here because the real connection
        # inherits from the thing that we are mocking out.  Take out
        # the reset if you want to see what I mean :)
        from vcr.patch import install, reset
        reset()
        self.real_connection = self._baseclass(*args, **kwargs)
        install(self.cassette)


class VCRHTTPConnection(VCRConnection):
    '''A Mocked class for HTTP requests'''
    _baseclass = HTTPConnection
    _protocol = 'http'


class VCRHTTPSConnection(VCRConnection):
    '''A Mocked class for HTTPS requests'''
    _baseclass = HTTPSConnection
    _protocol = 'https'
