import json
from six.moves import urllib, xmlrpc_client
from .util import read_body
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
    return read_body(r1) == read_body(r2)


def _header_checker(value, header='Content-Type'):
    def checker(headers):
        return value in headers.get(header, '').lower()
    return checker


def _transform_json(body):
    # Request body is always a byte string, but json.loads() wants a text
    # string. RFC 7159 says the default encoding is UTF-8 (although UTF-16
    # and UTF-32 are also allowed: hmmmmm).
    if body:
        return json.loads(body.decode('utf-8'))


_xml_header_checker = _header_checker('text/xml')
_xmlrpc_header_checker = _header_checker('xmlrpc', header='User-Agent')
_checker_transformer_pairs = (
    (_header_checker('application/x-www-form-urlencoded'), urllib.parse.parse_qs),
    (_header_checker('application/json'), _transform_json),
    (lambda request: _xml_header_checker(request) and _xmlrpc_header_checker(request), xmlrpc_client.loads),
)


def _identity(x):
    return x


def _get_transformer(request):
    for checker, transformer in _checker_transformer_pairs:
        if checker(request.headers):
            return transformer
    else:
        return _identity


def body(r1, r2):
    transformer = _get_transformer(r1)
    r2_transformer = _get_transformer(r2)
    if transformer != r2_transformer:
        transformer = _identity
    return transformer(read_body(r1)) == transformer(read_body(r2))


def headers(r1, r2):
    return r1.headers == r2.headers


def _log_matches(r1, r2, matches):
    differences = [m for m in matches if not m[0]]
    if differences:
        log.debug(
            "Requests {} and {} differ according to "
            "the following matchers: {}".format(r1, r2, differences)
        )


def requests_match(r1, r2, matchers):
    matches = [(m(r1, r2), m) for m in matchers]
    _log_matches(r1, r2, matches)
    return all(m[0] for m in matches)
