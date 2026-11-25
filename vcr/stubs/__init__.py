"""Stubs for patching HTTP and HTTPS requests"""

import json
import logging
from contextlib import suppress
from email.message import Message
from http.client import HTTPConnection, HTTPResponse, HTTPSConnection
from io import BytesIO

from vcr.errors import CannotOverwriteExistingCassetteException
from vcr.filters import AVAILABLE_DECOMPRESSORS
from vcr.request import Request

from . import compat

log = logging.getLogger(__name__)


class VCRFakeSocket:
    """
    A socket that doesn't do anything!
    Used when playing back cassettes, when there
    is no actual open socket.
    """

    def close(self):
        pass

    def settimeout(self, *args, **kwargs):
        pass

    def gettimeout(self):
        return None

    def recv(self, *args, **kwargs):
        # Nothing is ever waiting to be read. urllib3-future (niquests) peeks at
        # idle pooled connections with a non-blocking read before reusing them.
        raise BlockingIOError

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
            header_string += key.encode("utf-8") + b":" + v.encode("utf-8") + b"\r\n"
    return compat.get_httpmessage(header_string)


def serialize_headers(response):
    headers = response.headers if response.msg is None else response.msg
    out = {}
    for key, values in compat.get_headers(headers):
        out.setdefault(key, [])
        out[key].extend(values)
    return out


class VCRHTTPResponse(HTTPResponse):
    """
    Stub response class that gets returned instead of a HTTPResponse
    """

    def __init__(self, recorded_response, request_url=None):
        self.fp = None
        if request_url:
            self.url = request_url
        self.recorded_response = recorded_response
        self.reason = recorded_response["status"]["message"]
        self.status = self.code = recorded_response["status"]["code"]
        self.version = None
        self.version_string = None
        self._content = BytesIO(self.recorded_response["body"]["string"])
        self._decoded_content = None
        self._closed = False

        headers = self.recorded_response["headers"]
        # Since we are loading a response that has already been serialized, our
        # response is no longer chunked.  That means we don't want any
        # libraries trying to process a chunked response.  By removing the
        # transfer-encoding: chunked header, this should cause the downstream
        # libraries to process this as a non-chunked response.
        te_key = [h for h in headers if h.upper() == "TRANSFER-ENCODING"]
        if te_key:
            del headers[te_key[0]]
        self.headers = self.msg = parse_headers(headers)

        self.length = compat.get_header(self.msg, "content-length") or None

    @property
    def _original_response(self):
        # requests extracts cookies from _original_response.msg. urllib.request
        # replaces msg with the reason phrase, as it does on real responses,
        # which have no _original_response, so then there's none here either (#956).
        return self if isinstance(self.msg, Message) else None

    @property
    def closed(self):
        # in python3, I can't change the value of self.closed.  So I'
        # twiddling self._closed and using this property to shadow the real
        # self.closed from the superclass
        return self._closed

    def _decoded_body(self):
        """Body with its Content-Encoding undone.

        Cassettes recorded before raw storage kept an already-decoded
        body next to its Content-Encoding header; the decompressors
        return such a body unchanged, so those cassettes keep working.
        """
        raw = self.recorded_response["body"]["string"]
        encoding = None
        if isinstance(self.msg, Message):
            encoding = self.msg.get("content-encoding")
        if encoding:
            decompressor = AVAILABLE_DECOMPRESSORS.get(encoding.strip().lower())
            if decompressor is not None:
                return decompressor(raw)
        return raw

    def _body_for(self, decode_content):
        """Buffer a read should consume: the decoded body, unless
        decode_content is False, in which case the stored (raw) bytes."""
        if decode_content is False:
            return self._content
        if self._decoded_content is None:
            self._decoded_content = BytesIO(self._decoded_body())
        return self._decoded_content

    def read(self, *args, decode_content=None, **kwargs):
        content = self._body_for(decode_content)
        data = content.read(*args, **kwargs)
        if content.tell() == content.getbuffer().nbytes:
            # urllib3 returns the connection to its pool once the body is read (#949).
            self.release_conn()
        return data

    def read1(self, *args, **kwargs):
        return self._body_for(None).read1(*args, **kwargs)

    def readall(self):
        return self._body_for(None).readall()

    def readinto(self, *args, **kwargs):
        return self._body_for(None).readinto(*args, **kwargs)

    def readline(self, *args, **kwargs):
        return self._body_for(None).readline(*args, **kwargs)

    def readlines(self, *args, **kwargs):
        return self._body_for(None).readlines(*args, **kwargs)

    def seekable(self):
        return self._body_for(None).seekable()

    def tell(self):
        return self._body_for(None).tell()

    def isatty(self):
        return self._body_for(None).isatty()

    def seek(self, *args, **kwargs):
        return self._body_for(None).seek(*args, **kwargs)

    def close(self):
        self._closed = True
        return True

    def getcode(self):
        return self.status

    def isclosed(self):
        return self.closed

    def info(self):
        return parse_headers(self.recorded_response["headers"])

    def getheaders(self):
        message = parse_headers(self.recorded_response["headers"])
        return list(compat.get_header_items(message))

    def getheader(self, header, default=None):
        values = [v for (k, v) in self.getheaders() if k.lower() == header.lower()]

        if values:
            return ", ".join(values)
        else:
            return default

    def readable(self):
        return self._body_for(None).readable()

    @property
    def length_remaining(self):
        content = self._body_for(None)
        return content.getbuffer().nbytes - content.tell()

    def get_redirect_location(self):
        """
        Returns (a) redirect location string if we got a redirect
        status code and valid location, (b) None if redirect status and
        no location, (c) False if not a redirect status code.
        See https://urllib3.readthedocs.io/en/stable/reference/urllib3.response.html .
        """
        if not (300 <= self.status <= 399):
            return False
        return self.getheader("Location")

    @property
    def data(self):
        # urllib3's .data is the decoded body.
        return self._body_for(None).getbuffer().tobytes()

    def json(self):
        # urllib3 2.x responses can decode a JSON body themselves.
        return json.loads(self.data.decode("utf-8"))

    def drain_conn(self):
        pass

    def release_conn(self):
        # urllib3 attaches the leased connection even to a replayed response.
        pool = getattr(self, "_pool", None)
        connection = getattr(self, "_connection", None)
        if pool is not None and connection is not None:
            if getattr(connection, "_vcr_cassette_exited", False):
                connection = None  # its cassette took it out of the pool
            pool._put_conn(connection)
            self._connection = None

    def stream(self, amt=65536, decode_content=None):
        while True:
            b = self.read(amt, decode_content=decode_content)
            yield b
            if not b:
                break


class VCRConnection:
    # A reference to the cassette that's currently being patched in
    cassette = None

    def _port_postfix(self):
        """
        Returns empty string for the default port and ':port' otherwise
        """
        port = (
            self.real_connection.port
            if not self.real_connection._tunnel_host
            else self.real_connection._tunnel_port
        )
        default_port = {"https": 443, "http": 80}[self._protocol]
        return f":{port}" if port != default_port else ""

    def _real_host(self):
        """Returns the request host"""
        if self.real_connection._tunnel_host:
            # The real connection is to an HTTPS proxy
            return self.real_connection._tunnel_host
        else:
            return self.real_connection.host

    def _uri(self, url):
        """Returns request absolute URI"""
        if url and not url.startswith("/"):
            # Then this must be a proxy request.
            return url
        uri = f"{self._protocol}://{self._real_host()}{self._port_postfix()}{url}"
        log.debug("Absolute URI: %s", uri)
        return uri

    def _url(self, uri):
        """Returns request selector url from absolute URI"""
        prefix = f"{self._protocol}://{self._real_host()}{self._port_postfix()}"
        return uri.replace(prefix, "", 1)

    def request(self, method, url, body=None, headers=None, *args, **kwargs):
        """Persist the request metadata in self._vcr_request"""
        self._vcr_request = Request(method=method, uri=self._uri(url), body=body, headers=headers or {})
        log.debug(f"Got {self._vcr_request}")

        # Note: The request may not actually be finished at this point, so
        # I'm not sending the actual request until getresponse().  This
        # allows me to compare the entire length of the response to see if it
        # exists in the cassette.

        self._sock = VCRFakeSocket()

    def putrequest(self, method, url, *args, **kwargs):
        """
        httplib gives you more than one way to do it.  This is a way
        to start building up a request.  Usually followed by a bunch
        of putheader() calls.
        """
        self._vcr_request = Request(method=method, uri=self._uri(url), body="", headers={})
        log.debug(f"Got {self._vcr_request}")

    def putheader(self, header, *values):
        self._vcr_request.headers[header] = values

    def send(self, data):
        """
        This method is called after request(), to add additional data to the
        body of the request.  So if that happens, let's just append the data
        onto the most recent request in the cassette.
        """
        self._vcr_request.body = self._vcr_request.body + data if self._vcr_request.body else data

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
        """Retrieve the response"""
        # Check to see if the cassette has a response for this request. If so,
        # then return it
        if self.cassette.can_play_response_for(self._vcr_request):
            log.info(f"Playing response for {self._vcr_request} from cassette")
            response = self.cassette.play_response(self._vcr_request)
            return VCRHTTPResponse(response, self._vcr_request.uri)
        else:
            if self.cassette.write_protected and self.cassette.filter_request(self._vcr_request):
                raise CannotOverwriteExistingCassetteException(
                    cassette=self.cassette,
                    failed_request=self._vcr_request,
                )

            # Otherwise, we should send the request, then get the response
            # and return it.

            log.info(f"{self._vcr_request} not in cassette, sending to real server")
            # This is imported here to avoid circular import.
            # TODO(@IvanMalison): Refactor to allow normal import.
            from vcr.patch import force_reset

            with force_reset():
                if self.__dict__.get("_deferred_connect"):
                    args, kwargs = self._deferred_connect
                    self._deferred_connect = None
                    self.real_connection.connect(*args, **kwargs)
                try:
                    # Ask urllib3 for the raw bytes: with preloading, the
                    # body would be read and decoded before we ever see it,
                    # and the cassette would store a decoded body next to
                    # its Content-Encoding header (#1116). Other connections
                    # do not take these keywords and already return raw bytes.
                    self.real_connection.request(
                        method=self._vcr_request.method,
                        url=self._url(self._vcr_request.uri),
                        body=self._vcr_request.body_bytes,
                        headers=self._vcr_request.headers,
                        preload_content=False,
                        decode_content=False,
                    )
                except TypeError:
                    self.real_connection.request(
                        method=self._vcr_request.method,
                        url=self._url(self._vcr_request.uri),
                        body=self._vcr_request.body_bytes,
                        headers=self._vcr_request.headers,
                    )

            # get the response
            response = self.real_connection.getresponse()
            try:
                response_data = response.read(decode_content=False)
            except TypeError:
                response_data = response.data if hasattr(response, "data") else response.read()

            # put the response into the cassette
            response = {
                "status": {"code": response.status, "message": response.reason},
                "headers": serialize_headers(response),
                "body": {"string": response_data},
            }
            self.cassette.append(self._vcr_request, response)
        return VCRHTTPResponse(response, self._vcr_request.uri)

    def set_debuglevel(self, *args, **kwargs):
        self.real_connection.set_debuglevel(*args, **kwargs)

    def connect(self, *args, **kwargs):
        """
        httplib2 uses this, and urllib3 calls it before sending an HTTPS request.

        Only pass to the baseclass if we don't have a recorded response
        and are not write-protected.
        """

        if not hasattr(self, "_vcr_request"):
            # The request isn't known yet, so we can't tell whether it will be
            # played back. Connect only if it's sent (#515).
            self._deferred_connect = (args, kwargs)
            return

        if self.cassette.can_play_response_for(self._vcr_request):
            # We already have a response we are going to play, don't
            # actually connect
            return

        if self.cassette.write_protected:
            # Cassette is write-protected, don't actually connect
            return

        from vcr.patch import force_reset

        with force_reset():
            return self.real_connection.connect(*args, **kwargs)

        self._sock = VCRFakeSocket()

    @property
    def sock(self):
        if self.real_connection.sock:
            return self.real_connection.sock
        return self._sock

    @sock.setter
    def sock(self, value):
        if self.real_connection.sock:
            self.real_connection.sock = value

    def __init__(self, *args, **kwargs):
        kwargs.pop("strict", None)  # apparently this is gone in py3

        # need to temporarily reset here because the real connection
        # inherits from the thing that we are mocking out.  Take out
        # the reset if you want to see what I mean :)
        from vcr.patch import force_reset

        with force_reset():
            self.real_connection = self._baseclass(*args, **kwargs)

        self._sock = None

    def __setattr__(self, name, value):
        """
        We need to define this because any attributes that are set on the
        VCRConnection need to be propagated to the real connection.

        For example, urllib3 will set certain attributes on the connection,
        such as 'ssl_version'. These attributes need to get set on the real
        connection to have the correct and expected behavior.

        TODO: Separately setting the attribute on the two instances is not
        ideal. We should switch to a proxying implementation.
        """
        with suppress(AttributeError):
            setattr(self.real_connection, name, value)

        super().__setattr__(name, value)

    def __getattr__(self, name):
        """
        Send requests for weird attributes up to the real connection
        (counterpart to __setattr above)
        """
        if self.__dict__.get("real_connection"):
            # check in case real_connection has not been set yet, such as when
            # we're setting the real_connection itself for the first time
            return getattr(self.real_connection, name)

        return super().__getattr__(name)


for k, v in HTTPConnection.__dict__.items():
    if isinstance(v, staticmethod):
        setattr(VCRConnection, k, v)


class VCRHTTPConnection(VCRConnection):
    """A Mocked class for HTTP requests"""

    _baseclass = HTTPConnection
    _protocol = "http"
    debuglevel = _baseclass.debuglevel
    _http_vsn = _baseclass._http_vsn
    _http_vsn_str = getattr(_baseclass, "_http_vsn_str", None)


class VCRHTTPSConnection(VCRConnection):
    """A Mocked class for HTTPS requests"""

    _baseclass = HTTPSConnection
    _protocol = "https"
    is_verified = True
    debuglevel = _baseclass.debuglevel
    _http_vsn = _baseclass._http_vsn
    _http_vsn_str = getattr(_baseclass, "_http_vsn_str", None)
