from six.moves.urllib.parse import urlparse, parse_qsl


class Request(object):

    def __init__(self, method, uri, body, headers):
        self.method = method
        self.uri = uri
        self.body = body
        self.headers = {}
        for key in headers:
            self.add_header(key, headers[key])

    def add_header(self, key, value):
        value = list(value) if isinstance(value, (tuple, list)) else [value]
        self.headers.setdefault(key, []).extend(value)

    def flat_headers_dict(self):
        return dict((key, self.headers[key][0]) for key in self.headers)

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
            port = {'https': 433, 'http': 80}[parse_uri.scheme]
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
            'headers': self.headers,
        }

    @classmethod
    def _from_dict(cls, dct):
        return Request(**dct)
