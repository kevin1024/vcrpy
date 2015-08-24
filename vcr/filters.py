from six import BytesIO, text_type
from six.moves.urllib.parse import urlparse, urlencode, urlunparse
import json

from .compat import collections


def remove_headers(request, headers_to_remove):
    new_headers = request.headers.copy()
    for k in headers_to_remove:
        if k in new_headers:
            del new_headers[k]
    request.headers = new_headers
    return request


def remove_query_parameters(request, query_parameters_to_remove):
    query = request.query
    new_query = [(k, v) for (k, v) in query
                 if k not in query_parameters_to_remove]
    if len(new_query) != len(query):
        uri_parts = list(urlparse(request.uri))
        uri_parts[4] = urlencode(new_query)
        request.uri = urlunparse(uri_parts)
    return request


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
