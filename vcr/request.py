class Request(object):

    def __init__(self, protocol, host, port, method, path, body, headers):
        self.protocol = protocol
        self.host = host
        self.port = port
        self.method = method
        self.path = path
        self.body = body
        # make headers a frozenset so it will be hashable
        self.headers = frozenset(headers.items())

    @property
    def url(self):
        return "{0}://{1}{2}".format(self.protocol, self.host, self.path)

    def __key(self):
        return (
            self.host,
            self.port,
            self.method,
            self.path,
            self.body,
            self.headers
        )

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __str__(self):
        return "<Request ({0}) {1}>".format(self.method, self.url)

    def __repr__(self):
        return self.__str__()

    def _to_dict(self):
        return {
            'protocol': self.protocol,
            'host': self.host,
            'port': self.port,
            'method': self.method,
            'path': self.path,
            'body': self.body,
            'headers': self.headers,
        }

    @classmethod
    def _from_dict(cls, dct):
        return Request(**dct)
