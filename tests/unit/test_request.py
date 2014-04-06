from vcr.request import Request


def test_str():
    req = Request('GET', 'http://www.google.com:80/', '', {})
    str(req) == '<Request (GET) http://www.google.com:80/>'
