class Request(object):

    def __init__(self, host, port, method, url, body, headers):
        self.host = host
        self.port = port
        self.method = method
        self.url = url
        self.body = body
        self.headers = frozenset(headers.items())

    def __key(self):
        return (self.host, self.port, self.method, self.url, self.body, self.headers)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return hash(self) == hash(other)
