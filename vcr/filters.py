from six import BytesIO
from six.moves.urllib.parse import urlparse, urlencode, urlunparse
try:
    from collections import OrderedDict
except ImportError:
    from backport_collections import OrderedDict
import copy


def remove_headers(request, headers_to_remove):
    headers = copy.copy(request.headers)
    headers_to_remove = [h.lower() for h in headers_to_remove]
    keys = [k for k in headers if k.lower() in headers_to_remove]
    if keys:
        for k in keys:
            headers.pop(k)
        request.headers = headers
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
        post_data = OrderedDict()
        for k, sep, v in [p.partition(b'=') for p in request.body.split(b'&')]:
            if k in post_data:
                post_data[k].append(v)
            elif len(k) > 0 and k.decode('utf-8') not in post_data_parameters_to_remove:
                post_data[k] = [v]
        request.body = b'&'.join(
            b'='.join([k, v])
            for k, vals in post_data.items() for v in vals)
    return request
