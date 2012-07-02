import socket
from httplib import HTTPConnection, HTTPSConnection, HTTPMessage
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
        HTTPConnection.request(self, method, url, body=body, headers=headers)

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


class VCRHTTPSConnection(HTTPSConnection):
    """
    Note that this is pretty much a copy-and-paste of the
    VCRHTTPConnection class.  I couldn't figure out how to
    do multiple inheritance to get this to work without
    duplicating code.  These are old-style classes which
    I frankly don't understand.
    """

    def __init__(self, host, port=None, key_file=None, cert_file=None,
                         strict=None, timeout=socket._GLOBAL_DEFAULT_TIMEOUT,
                         source_address=None):
        """
        I override the init and copied a lot of the code from the parent
        class because HTTPConnection when this happens has been replaced
        by VCRHTTPConnection,  but doing it here lets us use the original
        one.
        """
        HTTPConnection.__init__(self, host, port, strict, timeout,
                                source_address)
        self.key_file = key_file
        self.cert_file = cert_file
        self._cassette = Cassette()

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
        HTTPSConnection.request(self, method, url, body=body, headers=headers)

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
