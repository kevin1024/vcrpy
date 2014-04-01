from six.moves.urllib.parse import urlparse, parse_qsl


def method(r1, r2):
    return r1.method == r2.method


def url(r1, r2):
    return r1.url == r2.url


def semantic_url(r1, r2):
    """Returns True if urls are semantically the same

    If the difference between urls is only in the order of query params
    then urls are considered semantically the same.
    """
    query_index = 4
    r1_url = list(urlparse(r1.url))
    r2_url = list(urlparse(r2.url))
    r1_qs = r1_url[query_index]
    r2_qs = r2_url[query_index]
    r1_url[query_index] = sorted(parse_qsl(r1_qs))
    r2_url[query_index] = sorted(parse_qsl(r2_qs))
    return r1_url == r2_url


def host(r1, r2):
    return r1.host == r2.host


def path(r1, r2):
    return r1.path == r2.path


def body(r1, r2):
    return r1.body == r2.body


def headers(r1, r2):
    return r1.headers == r2.headers


def requests_match(r1, r2, matchers):
    return all(m(r1, r2) for m in matchers)
