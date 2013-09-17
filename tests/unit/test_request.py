from vcr.request import Request


# Generates a body with places where the multipart boundaries are removed.
# Snippet taken from http://www.w3.org/TR/html401/interact/forms.html#h-17.13.4
def fake_multipart_message(boundary1, boundary2):
    return ({"Content-Type": "multipart/form-data; boundary=\"{0}\"".format(boundary1)}, """
    --{0}
    Content-Disposition: form-data; name="submit-name"

    Larry
    --{0}
    Content-Disposition: form-data; name="files"
    Content-Type: multipart/mixed; boundary={1}

    --{1}
    Content-Disposition: file; filename="file1.txt"
    Content-Type: text/plain

    ... contents of file1.txt ...
    --{1}
    Content-Disposition: file; filename="file2.gif"
    Content-Type: image/gif
    Content-Transfer-Encoding: binary

    ...contents of file2.gif...
    --{1}--
    --{0}--
    """.format(boundary1, boundary2))


def test_url():
    req = Request('http', 'www.google.com', 80, 'GET', '/', '', {})
    assert req.url == 'http://www.google.com/'


def test_str():
    req = Request('http', 'www.google.com', 80, 'GET', '/', '', {})
    str(req) == '<Request (GET) http://www.google.com>'


def test_hash_is_multipart_boundary_agnostic():
    header1, body1 = fake_multipart_message('foo', 'bar')
    header2, body2 = fake_multipart_message('baz', 'quux')
    req1 = Request('http', 'www.google.com', 80, 'POST', '/', body1, header1)
    req2 = Request('http', 'www.google.com', 80, 'POST', '/', body2, header2)
    assert hash(req1) == hash(req2)


def test_eq():
    header1, body1 = fake_multipart_message('foo', 'bar')
    header2, body2 = fake_multipart_message('baz', 'quux')
    req1 = Request('http', 'www.google.com', 80, 'POST', '/', body1, header1)
    req2 = Request('http', 'www.google.com', 80, 'POST', '/', body2, header2)
    assert req1 == req2
