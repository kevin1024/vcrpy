from six import BytesIO, text_type
from six.moves.urllib.parse import urlparse, urlencode, urlunparse
import json

from .compat import collections

def replace_headers(request, replacements):
    """
    Replace headers in request according to replacements. The replacements
    should be a list of (key, value) pairs where the value can be any of:
      1. A simple replacement string value.
      2. None to remove the given header.
      3. A callable which accepts (key, value, request) and returns a string
         value or None.
    """
    new_headers = request.headers.copy()
    for k, rv in replacements:
        if k in new_headers:
            ov = new_headers.pop(k)
            if callable(rv):
                rv = rv(key=k, value=ov, request=request)
            if rv is not None:
                new_headers[k] = rv
    request.headers = new_headers
    return request


def remove_headers(request, headers_to_remove):
    """
    Wrap replace_headers() for API backward compatibility.
    """
    replacements = [(k, None) for k in headers_to_remove]
    return replace_headers(request, replacements)


def replace_query_parameters(request, replacements):
    """
    Replace query parameters in request according to replacements. The
    replacements should be a list of (key, value) pairs where the value can be
    any of:
      1. A simple replacement string value.
      2. None to remove the given header.
      3. A callable which accepts (key, value, request) and returns a string
         value or None.
    """
    query = request.query
    new_query = []
    replacements = dict(replacements)
    for k, ov in query:
        if k not in replacements:
            new_query.append((k, ov))
        else:
            rv = replacements[k]
            if callable(rv):
                rv = rv(key=k, value=ov, request=request)
            if rv is not None:
                new_query.append((k, rv))
    uri_parts = list(urlparse(request.uri))
    uri_parts[4] = urlencode(new_query)
    request.uri = urlunparse(uri_parts)
    return request


def remove_query_parameters(request, query_parameters_to_remove):
    """
    Wrap replace_query_parameters() for API backward compatibility.
    """
    replacements = [(k, None) for k in query_parameters_to_remove]
    return replace_query_parameters(request, replacements)


def remove_post_data_parameters(request, post_data_parameters_to_remove):
    if request.method == 'POST' and not isinstance(request.body, BytesIO):
        if request.headers.get('Content-Type') == 'application/json':
            json_data = json.loads(request.body.decode('utf-8'))
            for k in list(json_data.keys()):
                if k in post_data_parameters_to_remove:
                    del json_data[k]
            request.body = json.dumps(json_data).encode('utf-8')
        else:
            post_data = collections.OrderedDict()
            if isinstance(request.body, text_type):
                request.body = request.body.encode('utf-8')

            for k, sep, v in (p.partition(b'=') for p in request.body.split(b'&')):
                if k in post_data:
                    post_data[k].append(v)
                elif len(k) > 0 and k.decode('utf-8') not in post_data_parameters_to_remove:
                    post_data[k] = [v]
            request.body = b'&'.join(
                b'='.join([k, v])
                for k, vals in post_data.items() for v in vals)
    return request
