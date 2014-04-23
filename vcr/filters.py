from six.moves.urllib.parse import urlparse, parse_qsl, urlunparse, urlencode
import copy


def _remove_headers(request, headers_to_remove):
    out = []
    for k, v in request.headers:
        if k.lower() not in [h.lower() for h in headers_to_remove]:
            out.append((k, v))
    request.headers = frozenset(out)
    return request


def _remove_query_parameters(request, query_parameters_to_remove):
    if not hasattr(request, 'path' or not query_parameters_to_remote):
        return request
    url = urlparse(request.url)
    q = parse_qsl(url.query)
    q = [(k, v) for k, v in q if k not in query_parameters_to_remove]
    if q:
        request.path = url.path + '?' + urlencode(q)
    else:
        request.path = url.path
    return request


def filter_request(
        request,
        filter_headers,
        filter_query_parameters,
        before_record
        ):
    request = copy.copy(request)  # don't mutate request object
    if hasattr(request, 'headers') and filter_headers:
        request = _remove_headers(request, filter_headers)
    if filter_query_parameters:
        request = _remove_query_parameters(request, filter_query_parameters)
    if before_record:
        request = before_record(request)
    return request
