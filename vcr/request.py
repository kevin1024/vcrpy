from six.moves.urllib.parse import urlparse, parse_qsl


class Request(object):

    def __init__(self, method, uri, body, headers):
        self.method = method
        self.uri = uri
        self.body = body
        # make headers a frozenset so it will be hashable
        self.headers = frozenset(headers.items())

    def add_header(self, key, value):
        tmp = dict(self.headers)
        tmp[key] = value
        self.headers = frozenset(tmp.iteritems())

    @property
    def host(self):
        return urlparse(self.uri).hostname

    @property
    def port(self):
        return urlparse(self.uri).port

    @property
    def url(self):
        return self.uri

    def __key(self):
        return (
            self.method,
            self.uri,
            self.body,
            self.headers
        )

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return hash(self) == hash(other)

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
