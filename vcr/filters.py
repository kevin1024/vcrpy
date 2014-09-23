from six.moves.urllib.parse import urlparse, urlencode, urlunparse
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
