'''Stubs for patching HTTP and HTTPS requests'''

HAS_PY3 = False
try:
    from httplib import HTTPConnection, HTTPSConnection, HTTPMessage
    from cStringIO import StringIO
except ImportError:
    import http.client
    from http.client import HTTPConnection, HTTPSConnection, HTTPMessage
    from io import StringIO
    HAS_PY3 = True
from io import BytesIO

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
    for key, val in header_dict.items():
        msg.addheader(key, val)
        msg.headers.append("{0}:{1}".format(key, val))
    return msg


def parse_headers(header_list):
    if HAS_PY3:
        try:
            return http.client.parse_headers(
                BytesIO(
                    b'\n'.join(
                        [b': '.join((k.encode('utf-8'), v.encode('utf-8')))
                         for k, v in header_list])
                    + b'\r\n'))
        except ValueError:
            return http.client.parse_headers(
                BytesIO(b'\n'.join([header.encode('utf-8')
                                    for header in header_list])))

    if isinstance(header_list, dict):
        return parse_headers_backwards_compat(header_list)
    headers = "".join(header_list) + "\r\n"
    msg = HTTPMessage(StringIO(headers))
    msg.fp.seek(0)
    msg.readheaders()
    return msg


def get_header(message, name):
    if HAS_PY3:
        return message.getallmatchingheaders(name)
    else:
        return message.getheader(name)


def get_header_items(message):
    if HAS_PY3:
        return dict(message._headers).items()
    else:
        return message.dict.items()


def get_headers(response):
    if HAS_PY3:
        return response.msg._headers
    else:
        return response.msg.headers


class VCRHTTPResponse(object):
    """
    Stub reponse class that gets returned instead of a HTTPResponse
    """
    def __init__(self, recorded_response):
        self.recorded_response = recorded_response
        self.reason = recorded_response['status']['message']
        self.status = self.code = recorded_response['status']['code']
        self.version = None
        self._content = BytesIO(self.recorded_response['body']['string'])
        self.closed = False

        headers = self.recorded_response['headers']
        self.msg = parse_headers(headers)

        self.length = get_header(self.msg, 'content-length') or None

    def read(self, *args, **kwargs):
        # Note: I'm pretty much ignoring any chunking stuff because
        # I don't really understand what it is or how it works.
        return self._content.read(*args, **kwargs)

    def readline(self, *args, **kwargs):
        return self._content.readline(*args, **kwargs)

    def close(self):
        self.closed = True
        return True

    def getcode(self):
        return self.status

    def isclosed(self):
        # Urllib3 seems to call this because it actually uses
        # the weird chunking support in httplib
        return self.closed

    def info(self):
        return parse_headers(self.recorded_response['headers'])

    def getheaders(self):
        message = parse_headers(self.recorded_response['headers'])
        return get_header_items(message)


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
            except TypeError:
                # If this is a file-like object, try to
                # fstat its file descriptor
                import os
                try:
                    thelen = str(os.fstat(body.fileno()).st_size)
                except (AttributeError, OSError):
                    # Don't send a length if this failed
                    if self.debuglevel > 0:
                        print("Cannot stat!!")

            if thelen is not None:
                self.putheader('Content-Length', thelen)
        for hdr, value in headers.items():
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
        self._buffer.extend((b"", b""))
        msg = b"\r\n".join(self._buffer)
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
                'headers': get_headers(response),
                'body': {'string': response.read()},
            }
            self.cassette.append(self._vcr_request, response)
        return VCRHTTPResponse(response)


class VCRHTTPConnection(VCRConnectionMixin, HTTPConnection):
    '''A Mocked class for HTTP requests'''
    # Can't use super since this is an old-style class
    _baseclass = HTTPConnection
    _protocol = 'http'


if HAS_PY3:
    class _InitOverride(object):
        """
         A sentinel to avoid circular super()
        """
        def __init__(self, *args, **kwargs):
            pass

        def init(self, host, port=None, key_file=None,
                 cert_file=None,
                 strict=http.client._strict_sentinel,
                 timeout=http.client.socket._GLOBAL_DEFAULT_TIMEOUT,
                 source_address=None, context=None,
                 check_hostname=None):
            HTTPSConnection.__init__(
                self, host, port=None, key_file=None, cert_file=None,
                strict=http.client._strict_sentinel,
                timeout=http.client.socket._GLOBAL_DEFAULT_TIMEOUT,
                source_address=None, context=None,
                check_hostname=None)
            HTTPConnection.__init__(
                self, host, port, strict, timeout, source_address)

    def dynamic_extend(obj, cls):
        if cls not in obj.__class__.__bases__:
            obj.__class__.__bases__ = (cls,) + obj.__class__.__bases__


class VCRHTTPSConnection(VCRConnectionMixin, HTTPSConnection):
    '''A Mocked class for HTTPS requests'''
    _baseclass = HTTPSConnection
    _protocol = 'https'

    def __init__(self, *args, **kwargs):
        '''I overrode the init and copied a lot of the code from the parent
        class because HTTPConnection when this happens has been replaced by
        VCRHTTPConnection,  but doing it here lets us use the original one.'''
        if HAS_PY3:
            # Due to HTTPSConnection calling super(HTTPSConnection,
            # self).__init__, where we have replaced HTTPSConnection
            # with this class, we get a cyclic recursion unless we
            # break the cycle.
            dynamic_extend(self, _InitOverride)
            super().init(*args, **kwargs)
        else:
            HTTPConnection.__init__(self, *args, **kwargs)
        self.key_file = kwargs.pop('key_file', None)
        self.cert_file = kwargs.pop('cert_file', None)
