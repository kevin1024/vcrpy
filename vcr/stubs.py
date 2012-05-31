from httplib import HTTPConnection, HTTPMessage
from cStringIO import StringIO
from .files import save_cassette, load_cassette
from .cassette import Cassette


class VCRHTTPResponse(object):
    def __init__(self, recorded_response):
        self.recorded_response = recorded_response
        self.reason = recorded_response['status']['message']
        self.status = recorded_response['status']['code']
        self._content = StringIO(self.recorded_response['body']['string'])

        self.msg = HTTPMessage(StringIO(''))
        for k, v in self.recorded_response['headers'].iteritems():
            self.msg.addheader(k, v)

    def read(self, chunked=False):
        return self._content.read()


class VCRHTTPConnection(HTTPConnection):

    def __init__(self, *args, **kwargs):
        self._cassette = Cassette()
        HTTPConnection.__init__(self, *args, **kwargs)

    def _save_cassette(self):
        save_cassette(self._vcr_cassette_path, self._cassette)

    def request(self, method, url, body=None, headers={}):
        old_cassette = load_cassette(self._vcr_cassette_path)
        if old_cassette:
            return
        self._cassette.requests.append(dict(
            method=method,
            url=url,
            body=body,
            headers=headers
        ))
        return HTTPConnection.request(self, method, url, body=body, headers=headers)

    def getresponse(self, buffering=False):
        old_cassette = load_cassette(self._vcr_cassette_path)
        if old_cassette:
            return VCRHTTPResponse(old_cassette[0]['response'])
        response = HTTPConnection.getresponse(self)
        self._cassette.responses.append({
            'status': {'code': response.status, 'message': response.reason},
            'headers': dict(response.getheaders()),
            'body': {'string': response.read()},
        })
        self._save_cassette()
        return VCRHTTPResponse(self._cassette[0]['response'])


class VCRHTTPSConnection(VCRHTTPConnection):
    pass
