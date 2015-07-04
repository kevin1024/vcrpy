import json
from six.moves import urllib, xmlrpc_client
import logging
log = logging.getLogger(__name__)


def method(r1, r2):
    return r1.method == r2.method


def uri(r1, r2):
    return r1.uri == r2.uri


def host(r1, r2):
    return r1.host == r2.host


def scheme(r1, r2):
    return r1.scheme == r2.scheme


def port(r1, r2):
    return r1.port == r2.port


def path(r1, r2):
    return r1.path == r2.path


def query(r1, r2):
    return r1.query == r2.query


def raw_body(r1, r2):
    if hasattr(r1.body, 'read') and hasattr(r2.body, 'read'):
        return r1.body.read() == r2.body.read()
    return r1.body == r2.body


def body(r1, r2):
    if hasattr(r1.body, 'read') and hasattr(r2.body, 'read'):
        r1_body = r1.body.read()
        r2_body  = r2.body.read()
    else:
        r1_body = r1.body
        r2_body  = r2.body
    if r1.headers.get('Content-Type') == r2.headers.get('Content-Type') == 'application/x-www-form-urlencoded':
        return urllib.parse.parse_qs(r1_body) == urllib.parse.parse_qs(r2_body)
    if r1.headers.get('Content-Type') == r2.headers.get('Content-Type') == 'application/json':
        return json.loads(r1_body) == json.loads(r2_body)
    if ('xmlrpc' in r1.headers.get('User-Agent', '') and 'xmlrpc' in r2.headers.get('User-Agent', '') and
        r1.headers.get('Content-Type') == r2.headers.get('Content-Type') == 'text/xml'):
        return xmlrpc_client.loads(r1_body) == xmlrpc_client.loads(r2_body)
    return r1_body == r2_body


def headers(r1, r2):
    return r1.headers == r2.headers


def _log_matches(r1, r2, matches):
    differences = [m for m in matches if not m[0]]
    if differences:
        log.debug(
            "Requests {0} and {1} differ according to "
            "the following matchers: {2}".format(r1, r2, differences)
        )


def requests_match(r1, r2, matchers):
    matches = [(m(r1, r2), m) for m in matchers]
    _log_matches(r1, r2, matches)
    return all([m[0] for m in matches])
