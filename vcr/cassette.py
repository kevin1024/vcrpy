class Cassette(object):
    def __init__(self, ser_cassette=None):
        self.requests = []
        self.responses = []
        if ser_cassette:
            self._unserialize(ser_cassette)

    def serialize(self):
        return ([{
            'request': req,
            'response': res,
        }  for req, res in zip(self.requests, self.responses)])

    def _unserialize(self, source):
        self.requests, self.responses = [r['request'] for r in source], [r['response'] for r in source]

    def get_request(self, match):
        try:
            return self.requests[self.requests.index(match)]
        except ValueError:
            return None

    def get_response(self, match):
        try:
            return self.responses[self.requests.index(match)]
        except ValueError:
            return None
