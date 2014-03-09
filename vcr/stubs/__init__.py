'''Stubs for patching HTTP and HTTPS requests'''

from httplib import HTTPConnection, HTTPSConnection, HTTPMessage, HTTPResponse
from cStringIO import StringIO

from vcr.request import Request
from vcr.errors import CannotOverwriteExistingCassetteException


def parse_headers_backwards_compat(header_dict):
    """
    In vcr 0.6.0, I changed the cassettes to store
    headers as a list instead of a dict.  This method
    parses the old dictionary-style headers for
    backwards-compatability reasons.
    """
    msg = HTTPMessage(StringIO(""))
    for key, val in header_dict.iteritems():
        msg.addheader(key, val)
        msg.headers.append("{0}:{1}".format(key, val))
    return msg


def parse_headers(header_list):
    if isinstance(header_list, dict):
        return parse_headers_backwards_compat(header_list)
    headers = "".join(header_list) + "\r\n"
    msg = HTTPMessage(StringIO(headers))
    msg.fp.seek(0)
    msg.readheaders()
    return msg


class VCRHTTPResponse(HTTPResponse):
    """
    Stub reponse class that gets returned instead of a HTTPResponse
    """
    def __init__(self, recorded_response):
        self.recorded_response = recorded_response
        self.reason = recorded_response['status']['message']
        self.status = recorded_response['status']['code']
        self.version = None
        self._content = StringIO(self.recorded_response['body']['string'])
        self.closed = False

        headers = self.recorded_response['headers']
        self.msg = parse_headers(headers)

        self.length = self.msg.getheader('content-length') or None

    def read(self, *args, **kwargs):
        # Note: I'm pretty much ignoring any chunking stuff because
        # I don't really understand what it is or how it works.
        return self._content.read(*args, **kwargs)

    def close(self):
        self.closed = True
        return True

    def isclosed(self):
        # Urllib3 seems to call this because it actually uses
        # the weird chunking support in httplib
        return self.closed

    def getheaders(self):
        headers = parse_headers(self.recorded_response['headers'])
        return headers.dict.iteritems()


class VCRConnectionMixin:
    # A reference to the cassette that's currently being patched in
    cassette = None

    def request(self, method, url, body=None, headers=None):
        '''Persist the request metadata in self._vcr_request'''
        # see VCRConnectionMixin._restore_socket for the motivation here
        if hasattr(self, 'sock'):
            del self.sock

        self._vcr_request = Request(
            protocol=self._protocol,
            host=self.host,
            port=self.port,
            method=method,
            path=url,
            body=body,
            headers=headers or {}
        )

        # Note: The request may not actually be finished at this point, so
        # I'm not sending the actual request until getresponse().  This
        # allows me to compare the entire length of the response to see if it
        # exists in the cassette.

    def send(self, data):
        '''
        This method is called after request(), to add additional data to the
        body of the request.  So if that happens, let's just append the data
        onto the most recent request in the cassette.
        '''
        self._vcr_request.body = (self._vcr_request.body or '') + data

    def close(self):
        self._restore_socket()
        self._baseclass.close(self)

    def _restore_socket(self):
        """
        Since some libraries (REQUESTS!!) decide to set options on
        connection.socket, I need to delete the socket attribute
        (which makes requests think this is a AppEngine connection)
        and then restore it when I want to make the actual request.
        This function restores it to its standard initial value
        (which is None)
        """
        if not hasattr(self, 'sock'):
            self.sock = None

    def _send_request(self, method, url, body, headers):
        """
        Copy+pasted from python stdlib 2.6 source because it
        has a call to self.send() which I have overridden
        #stdlibproblems #fml
        """
        header_names = dict.fromkeys([k.lower() for k in headers])
        skips = {}
        if 'host' in header_names:
            skips['skip_host'] = 1
        if 'accept-encoding' in header_names:
            skips['skip_accept_encoding'] = 1

        self.putrequest(method, url, **skips)

        if body and ('content-length' not in header_names):
            thelen = None
            try:
                thelen = str(len(body))
            except TypeError, te:
                # If this is a file-like object, try to
                # fstat its file descriptor
                import os
                try:
                    thelen = str(os.fstat(body.fileno()).st_size)
                except (AttributeError, OSError):
                    # Don't send a length if this failed
                    if self.debuglevel > 0:
                        print "Cannot stat!!"

            if thelen is not None:
                self.putheader('Content-Length', thelen)
        for hdr, value in headers.iteritems():
            self.putheader(hdr, value)
        self.endheaders()

        if body:
            self._baseclass.send(self, body)

    def _send_output(self, message_body=None):
        """
        Copy-and-pasted from httplib, just so I can modify the self.send()
        calls to call the superclass's send(), since I had to override the
        send() behavior, since send() is both an external and internal
        httplib API.
        """
        self._buffer.extend(("", ""))
        msg = "\r\n".join(self._buffer)
        del self._buffer[:]
        # If msg and message_body are sent in a single send() call,
        # it will avoid performance problems caused by the interaction
        # between delayed ack and the Nagle algorithm.
        if isinstance(message_body, str):
            msg += message_body
            message_body = None
        self._restore_socket()
        self._baseclass.send(self, msg)
        if message_body is not None:
            #message_body was not a string (i.e. it is a file) and
            #we must run the risk of Nagle
            self._baseclass.send(self, message_body)

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

           # restore sock's value to None, since we need a real socket
            self._restore_socket()

            #make the actual request
            self._baseclass.request(
                self,
                method=self._vcr_request.method,
                url=self._vcr_request.path,
                body=self._vcr_request.body,
                headers=dict(self._vcr_request.headers or {})
            )

            # get the response
            response = self._baseclass.getresponse(self)

            # put the response into the cassette
            response = {
                'status': {
                    'code': response.status,
                    'message': response.reason
                },
                'headers': response.msg.headers,
                'body': {'string': response.read()},
            }
            self.cassette.append(self._vcr_request, response)
        return VCRHTTPResponse(response)

    def connect(self):
        """
        Connect to the real server only when is neccesary.

        I need to override this method because httplib2 calls to conn.connect
        on the first request.

        """

        if not self.cassette.write_protected:
            return self._baseclass.connect(self)


class VCRHTTPConnection(VCRConnectionMixin, HTTPConnection):
    '''A Mocked class for HTTP requests'''
    # Can't use super since this is an old-style class
    _baseclass = HTTPConnection
    _protocol = 'http'

    def __init__(self, *args, **kwargs):
        '''I overrode the init because I need to clean kwargs before calling
        HTTPConnection.__init__.'''

        # Delete the keyword arguments that HTTPSConnection would not recognize
        safe_keys = set(('host', 'port', 'strict', 'timeout', 'source_address'))
        unknown_keys = set(kwargs.keys()) - safe_keys
        safe_kwargs = kwargs.copy()
        for kw in unknown_keys:
            del safe_kwargs[kw]

        self.proxy_info = kwargs.pop('proxy_info', None)
        HTTPConnection.__init__(self, *args, **safe_kwargs)


class VCRHTTPSConnection(VCRConnectionMixin, HTTPSConnection):
    '''A Mocked class for HTTPS requests'''
    _baseclass = HTTPSConnection
    _protocol = 'https'

    def __init__(self, *args, **kwargs):
        '''I overrode the init and copied a lot of the code from the parent
        class because HTTPConnection when this happens has been replaced by
        VCRHTTPConnection,  but doing it here lets us use the original one.'''

        # Delete the keyword arguments that HTTPSConnection would not recognize
        safe_keys = set(('host', 'port', 'key_file', 'cert_file', 'strict',
                     'timeout', 'source_address'))
        unknown_keys = set(kwargs.keys()) - safe_keys
        safe_kwargs = kwargs.copy()
        for kw in unknown_keys:
            del safe_kwargs[kw]

        self.proxy_info = kwargs.pop('proxy_info', None)
        if not 'ca_certs' in kwargs or kwargs['ca_certs'] is None:
            try:
                import httplib2
                self.ca_certs = httplib2.CA_CERTS
            except ImportError:
                self.ca_certs = None
        else:
            self.ca_certs = kwargs['ca_certs']

        self.disable_ssl_certificate_validation = kwargs.pop(
            'disable_ssl_certificate_validation', None)
        HTTPConnection.__init__(self, *args, **safe_kwargs)
        self.key_file = kwargs.pop('key_file', None)
        self.cert_file = kwargs.pop('cert_file', None)
