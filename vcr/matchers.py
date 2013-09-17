def method(r1, r2):
    return r1.method == r2.method


def url(r1, r2):
    return r1.url == r2.url


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
