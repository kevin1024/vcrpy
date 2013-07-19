from httplib import HTTPConnection, HTTPSConnection, HTTPMessage
from cStringIO import StringIO
from .files import save_cassette, load_cassette
from .cassette import Cassette


class VCRHTTPResponse(object):
    """
    Stub reponse class that gets returned instead of a HTTPResponse
    """
    def __init__(self, recorded_response):
        self.recorded_response = recorded_response
        self.reason = recorded_response['status']['message']
        self.status = recorded_response['status']['code']
        self.version = None
        self._content = StringIO(self.recorded_response['body']['string'])

        self.msg = HTTPMessage(StringIO(''))
        for k, v in self.recorded_response['headers'].iteritems():
            self.msg.addheader(k, v)

        self.length = self.msg.getheader('content-length') or None

    def read(self, *args, **kwargs):
        # Note: I'm pretty much ignoring any chunking stuff because
        # I don't really understand what it is or how it works.
        return self._content.read(*args, **kwargs)
        
    def close(self):
        return True

    def isclosed(self):
        # Urllib3 seems to call this because it actually uses
        # the weird chunking support in httplib
        return True

    def getheaders(self):
        return self.recorded_response['headers'].iteritems()


class VCRConnectionMixin:
    def _load_old_response(self):
        old_cassette = load_cassette(self._vcr_cassette_path)
        if old_cassette:
            return old_cassette.get_response(self._vcr)

    def request(self, method, url, body=None, headers={}):
        """
        Persist the request metadata in self._vcr
        """
        self._vcr = {
            'method': method,
            'url': url,
            'body': body,
            'headers': headers,
        }
        old_cassette = load_cassette(self._vcr_cassette_path)
        if old_cassette and old_cassette.get_request(self._vcr):
            return
        self._cassette.requests.append(dict(
            method=method,
            url=url,
            body=body,
            headers=headers
        ))
        self._baseclass.request(self, method, url, body=body, headers=headers)

    def getresponse(self, buffering=False):
        old_response = self._load_old_response()
        if not old_response:
            response = HTTPConnection.getresponse(self)
            self._cassette.responses.append({
                'status': {'code': response.status, 'message': response.reason},
                'headers': dict(response.getheaders()),
                'body': {'string': response.read()},
            })
            save_cassette(self._vcr_cassette_path, self._cassette)
        old_response = self._load_old_response()
        return VCRHTTPResponse(old_response)


class VCRHTTPConnection(VCRConnectionMixin, HTTPConnection):

    # Can't use super since this is an old-style class
    _baseclass = HTTPConnection

    def __init__(self, *args, **kwargs):
        self._cassette = Cassette()
        HTTPConnection.__init__(self, *args, **kwargs)


class VCRHTTPSConnection(VCRConnectionMixin, HTTPSConnection):

    _baseclass = HTTPSConnection

    def __init__(self, *args, **kwargs):
        """
        I overrode the init and copied a lot of the code from the parent
        class because HTTPConnection when this happens has been replaced
        by VCRHTTPConnection,  but doing it here lets us use the original
        one.
        """
        HTTPConnection.__init__(self, *args, **kwargs)
        self.key_file = kwargs.pop('key_file', None)
        self.cert_file = kwargs.pop('cert_file', None)
        self._cassette = Cassette()
