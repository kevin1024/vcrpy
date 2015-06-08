'''Stubs for patching HTTP and HTTPS requests'''

try:
    import http.client
except ImportError:
    pass
import logging
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

log = logging.getLogger(__name__)


class VCRFakeSocket(object):
    """
    A socket that doesn't do anything!
    Used when playing back casssettes, when there
    is no actual open socket.
    """

    def close(self):
        pass

    def settimeout(self, *args, **kwargs):
        pass

    def fileno(self):
        """
        This is kinda crappy.  requests will watch
        this descriptor and make sure it's not closed.
        Return file descriptor 0 since that's stdin.
        """
        return 0  # wonder how bad this is....


def parse_headers(header_list):
    """
    Convert headers from our serialized dict with lists for keys to a
    HTTPMessage
    """
    header_string = b""
    for key, values in header_list.items():
        for v in values:
            header_string += \
                key.encode('utf-8') + b":" + v.encode('utf-8') + b"\r\n"
    return compat.get_httpmessage(header_string)


def serialize_headers(response):
    out = {}
    for key, values in compat.get_headers(response.msg):
        out.setdefault(key, [])
        out[key].extend(values)
    return out


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
        # Since we are loading a response that has already been serialized, our
        # response is no longer chunked.  That means we don't want any
        # libraries trying to process a chunked response.  By removing the
        # transfer-encoding: chunked header, this should cause the downstream
        # libraries to process this as a non-chunked response.
        te_key = [h for h in headers.keys() if h.upper() == 'TRANSFER-ENCODING']
        if te_key:
            del headers[te_key[0]]
        self.headers = self.msg = parse_headers(headers)

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
        return list(compat.get_header_items(message))

    def getheader(self, header, default=None):
        values = [v for (k, v) in self.getheaders() if k.lower() == header.lower()]

        if values:
            return ', '.join(values)
        else:
            return default


class VCRConnection(object):
    # A reference to the cassette that's currently being patched in
    cassette = None

    def _port_postfix(self):
        """
        Returns empty string for the default port and ':port' otherwise
        """
        port = self.real_connection.port
        default_port = {'https': 443, 'http': 80}[self._protocol]
        return ':{0}'.format(port) if port != default_port else ''

    def _uri(self, url):
        """Returns request absolute URI"""
        uri = "{0}://{1}{2}{3}".format(
            self._protocol,
            self.real_connection.host,
            self._port_postfix(),
            url,
        )
        return uri

    def _url(self, uri):
        """Returns request selector url from absolute URI"""
        prefix = "{0}://{1}{2}".format(
            self._protocol,
            self.real_connection.host,
            self._port_postfix(),
        )
        return uri.replace(prefix, '', 1)

    def request(self, method, url, body=None, headers=None):
        '''Persist the request metadata in self._vcr_request'''
        self._vcr_request = Request(
            method=method,
            uri=self._uri(url),
            body=body,
            headers=headers or {}
        )
        log.debug('Got {0}'.format(self._vcr_request))

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
            method=method,
            uri=self._uri(url),
            body="",
            headers={}
        )
        log.debug('Got {0}'.format(self._vcr_request))

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

    def endheaders(self, message_body=None):
        """
        Normally, this would actually send the request to the server.
        We are not sending the request until getting the response,
        so bypass this part and just append the message body, if any.
        """
        if message_body is not None:
            self._vcr_request.body = message_body

    def getresponse(self, _=False, **kwargs):
        '''Retrieve the response'''
        # Check to see if the cassette has a response for this request. If so,
        # then return it
        if self.cassette.can_play_response_for(self._vcr_request):
            log.info(
                "Playing response for {0} from cassette".format(
                    self._vcr_request
                )
            )
            response = self.cassette.play_response(self._vcr_request)
            return VCRHTTPResponse(response)
        else:
            if self.cassette.write_protected and self.cassette.filter_request(
                self._vcr_request
            ):
                raise CannotOverwriteExistingCassetteException(
                    "No match for the request (%r) was found. "
                    "Can't overwrite existing cassette (%r) in "
                    "your current record mode (%r)."
                    % (self._vcr_request, self.cassette._path,
                       self.cassette.record_mode)
                )

            # Otherwise, we should send the request, then get the response
            # and return it.

            log.info(
                "{0} not in cassette, sending to real server".format(
                    self._vcr_request
                )
            )
            # This is imported here to avoid circular import.
            # TODO(@IvanMalison): Refactor to allow normal import.
            from vcr.patch import force_reset
            with force_reset():
                self.real_connection.request(
                    method=self._vcr_request.method,
                    url=self._url(self._vcr_request.uri),
                    body=self._vcr_request.body,
                    headers=self._vcr_request.headers,
                )

            # get the response
            response = self.real_connection.getresponse()

            # put the response into the cassette
            response = {
                'status': {
                    'code': response.status,
                    'message': response.reason
                },
                'headers': serialize_headers(response),
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
                self.cassette.can_play_response_for(self._vcr_request):
            # We already have a response we are going to play, don't
            # actually connect
            return

        if self.cassette.write_protected:
            # Cassette is write-protected, don't actually connect
            return

        return self.real_connection.connect(*args, **kwargs)

    @property
    def sock(self):
        if self.real_connection.sock:
            return self.real_connection.sock
        return VCRFakeSocket()

    @sock.setter
    def sock(self, value):
        if self.real_connection.sock:
            self.real_connection.sock = value

    def __init__(self, *args, **kwargs):
        if six.PY3:
            kwargs.pop('strict', None) # apparently this is gone in py3

        # need to temporarily reset here because the real connection
        # inherits from the thing that we are mocking out.  Take out
        # the reset if you want to see what I mean :)
        from vcr.patch import force_reset
        with force_reset():
            self.real_connection = self._baseclass(*args, **kwargs)


class VCRHTTPConnection(VCRConnection):
    '''A Mocked class for HTTP requests'''
    _baseclass = HTTPConnection
    _protocol = 'http'


class VCRHTTPSConnection(VCRConnection):
    '''A Mocked class for HTTPS requests'''
    _baseclass = HTTPSConnection
    _protocol = 'https'
    is_verified = True
