import warnings
from six import BytesIO, text_type
from six.moves.urllib.parse import urlparse, parse_qsl
from .util import HeadersDict


class Request(object):
    """Represent an HTTP request in vcrpy."""

    def __init__(self, method, uri, body, headers):
        self.method = method
        self.uri = uri
        self._was_file = hasattr(body, 'read')
        if self._was_file:
            self.body = body.read()
        else:
            self.body = body
        self.headers = headers

    @property
    def headers(self):
        return self._headers

    @headers.setter
    def headers(self, value):
        if not isinstance(value, HeadersDict):
            value = HeadersDict(value)
        self._headers = value

    @property
    def body(self):
        return BytesIO(self._body) if self._was_file else self._body

    @body.setter
    def body(self, value):
        if isinstance(value, text_type):
            value = value.encode('utf-8')
        self._body = value

    def add_header(self, key, value):
        warnings.warn("Request.add_header is deprecated. "
                      "Please assign to request.headers instead.",
                      DeprecationWarning)
        self.headers[key] = value

    @property
    def scheme(self):
        return urlparse(self.uri).scheme

    @property
    def host(self):
        return urlparse(self.uri).hostname

    @property
    def port(self):
        parse_uri = urlparse(self.uri)
        port = parse_uri.port
        if port is None:
            port = {'https': 443, 'http': 80}[parse_uri.scheme]
        return port

    @property
    def path(self):
        return urlparse(self.uri).path

    @property
    def query(self):
        q = urlparse(self.uri).query
        return sorted(parse_qsl(q))

    # alias for backwards compatibility
    @property
    def url(self):
        return self.uri

    # alias for backwards compatibility
    @property
    def protocol(self):
        return self.scheme

    def __str__(self):
        return "<Request ({0}) {1}>".format(self.method, self.uri)

    def __repr__(self):
        return self.__str__()

    def _to_dict(self):
        return {
            'method': self.method,
            'uri': self.uri,
            'body': self.body,
            'headers': self.headers.serialize,
        }

    @classmethod
    def _from_dict(cls, dct):
        return Request(**dct)
