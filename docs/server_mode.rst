Server Mode
===========

By default VCR.py works by patching HTTP client libraries. Server mode
records and replays HTTP traffic **without patching anything**: while a
cassette is open, VCR.py runs a real HTTP server on ``127.0.0.1``, and
your code sends its requests to that server instead of to the real API.

For every request the server receives, it:

1. replays the matching response from the cassette, if there is one;
2. otherwise, if the record mode allows it, forwards the request to the
   real ``base_url``, records the interaction and returns the real
   response;
3. otherwise, answers with an error response (see `Errors`_).

Because nothing is patched, server mode works with any HTTP client, in
any library and on any event loop, as long as you can point the client at
a different base URL.

Cassettes are the same in both modes: the recorded request URI is the real
one (``base_url`` + path), so a cassette recorded in one mode replays in the
other.

Quick start
-----------

Server mode is turned on by passing ``base_url``. The local server's
address is available as ``cassette.url``:

.. code:: python

    import requests
    import vcr

    with vcr.use_cassette("fixtures/octocat.yaml", base_url="https://api.github.com") as cass:
        # cass.url is something like "http://127.0.0.1:53817"
        response = requests.get(cass.url + "/users/octocat")
        assert response.json()["login"] == "octocat"

The first run forwards the request to ``https://api.github.com/users/octocat``
and records it. Later runs replay it from the cassette without any network
access.

Usually the code under test builds its own URLs from a configurable base
URL, so you only need to pass ``cass.url`` to it:

.. code:: python

    with vcr.use_cassette("fixtures/octocat.yaml", base_url="https://api.github.com") as cass:
        client = GitHubClient(base_url=cass.url)
        assert client.get_user("octocat").login == "octocat"

A ``base_url`` can contain a path prefix. Paths requested from the local
server are appended to it:

.. code:: python

    with vcr.use_cassette("users.yaml", base_url="https://example.com/api/v1") as cass:
        requests.get(cass.url + "/users")  # forwarded to https://example.com/api/v1/users

Fixed ports
~~~~~~~~~~~

By default the server listens on a free port chosen by the operating
system. If your configuration needs a URL known in advance, set
``server_port``:

.. code:: python

    my_vcr = vcr.VCR(base_url="https://api.github.com", server_port=8765)

    @my_vcr.use_cassette
    def test_octocat():
        assert requests.get("http://127.0.0.1:8765/users/octocat").ok

The port is released when the cassette closes, so the next cassette can
use it right away.

Decorators and test frameworks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With decorators, use ``inject_cassette=True`` to get the URL of a server on
a random port:

.. code:: python

    @vcr.use_cassette(base_url="https://api.github.com", inject_cassette=True)
    def test_octocat(cass):
        assert requests.get(cass.url + "/users/octocat").ok

With ``VCRTestCase``, return ``base_url`` from ``_get_vcr_kwargs`` and use
``self.cassette.url``:

.. code:: python

    from vcr.unittest import VCRTestCase

    class GitHubTest(VCRTestCase):
        def _get_vcr_kwargs(self, **kwargs):
            return {"base_url": "https://api.github.com"}

        def test_octocat(self):
            assert requests.get(self.cassette.url + "/users/octocat").ok

With pytest, a small fixture is often all you need:

.. code:: python

    import pytest
    import vcr

    my_vcr = vcr.VCR(base_url="https://api.github.com", cassette_library_dir="tests/cassettes")

    @pytest.fixture
    def github(request):
        with my_vcr.use_cassette(request.node.name + ".yaml") as cass:
            yield GitHubClient(base_url=cass.url)

    def test_octocat(github):
        assert github.get_user("octocat").login == "octocat"

Options
-------

These options can be passed to ``vcr.VCR(...)`` as defaults, or to
``use_cassette(...)`` for a single cassette. All other options
(record modes, matchers, filters, serializers, persisters...) work as in
patch mode.

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Option
     - Default
     - Meaning
   * - ``base_url``
     - ``None``
     - The real API, e.g. ``https://api.example.com/v1``. Setting it turns server mode on;
       ``base_url=None`` on a cassette turns it off again.
   * - ``server_host``
     - ``"127.0.0.1"``
     - Address the local server binds to.
   * - ``server_port``
     - ``0``
     - Port of the local server; ``0`` picks a free port.
   * - ``verify_upstream_ssl``
     - ``True``
     - Verify the certificate of an ``https`` ``base_url``. ``False`` disables verification; an
       ``ssl.SSLContext`` is used as is.
   * - ``upstream_timeout``
     - ``None``
     - Socket timeout, in seconds, for forwarded requests.

Errors
------

When a request can't be answered (for example a new request with
``record_mode="none"``, or an unreachable ``base_url``), the exception
can't be raised inside your HTTP client, which lives in another thread
or process. Instead:

- the client receives a response with status ``599``, an ``X-VCR-Error``
  header holding the exception's name, and the error message as body;
- the exception is stored in ``cassette.errors``;
- when the cassette closes, the first stored exception is raised (for
  example ``CannotOverwriteExistingCassetteException``), so the test
  fails even if your code swallowed the ``599``.

If your own code raises an exception inside the cassette, that exception
is the one you see.

.. code:: python

    from vcr.errors import CannotOverwriteExistingCassetteException

    with pytest.raises(CannotOverwriteExistingCassetteException):
        with vcr.use_cassette("users.yaml", base_url=API, record_mode="none") as cass:
            response = requests.get(cass.url + "/not-recorded")
            assert response.status_code == 599

What the server changes
-----------------------

The server tries to be transparent, with a few necessary exceptions:

- **Connection headers.** ``Host``, ``Connection``, ``Transfer-Encoding``,
  ``Expect`` and the other hop-by-hop headers belong to a single
  connection: they are not forwarded or recorded. The forwarded request
  gets the ``Host`` of ``base_url``.
- **Response framing.** Responses are sent with a ``Content-Length``
  instead of chunked encoding. Bodies are sent byte for byte as recorded,
  so compressed bodies stay compressed (unless you use
  ``decode_compressed_response=True``).
- **Redirects.** A ``Location`` header pointing into ``base_url`` is
  rewritten to point at the local server, so the client keeps going
  through VCR.py. Redirects to other hosts are left alone, and the client
  follows them directly, without VCR.py.
- **Cookies.** ``Domain`` and ``Secure`` are removed from ``Set-Cookie``
  headers, and a ``Path`` under the ``base_url`` prefix is shortened
  accordingly, so clients send the cookies back to ``127.0.0.1``.

These rewrites only affect what the client receives; the cassette always
keeps the original headers.

Filters and ignored hosts
-------------------------

``filter_headers``, ``filter_query_parameters``,
``filter_post_data_parameters`` and ``before_record_request`` change what
is **recorded and matched**. The real API always receives the real
request, so you can filter secrets out of cassettes without breaking
authentication while recording.

Requests ignored through ``ignore_hosts``, ``ignore_localhost`` or a
``before_record_request`` that returns ``None`` are forwarded but never
recorded, whatever the record mode is (as in patch mode).

Client notes
------------

- **aiohttp**: the default cookie jar ignores cookies set by IP
  addresses. If your test relies on cookies, use
  ``aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))``.
- **Proxy environment variables**: clients that honour ``HTTP_PROXY`` or
  ``HTTPS_PROXY`` may try to reach ``127.0.0.1`` through your proxy. Set
  ``NO_PROXY=127.0.0.1`` (or disable proxies on the client).
- **boto3 / AWS SDKs**: pass ``endpoint_url=cass.url``. Replaying works,
  but recording against real AWS doesn't: requests are signed (SigV4) for
  ``127.0.0.1:<port>``, and AWS rejects them once they're forwarded to the
  real host.
- **SDKs with hard-coded URLs**: server mode needs a way to change the base
  URL. If an SDK doesn't offer one, use patch mode.

Limitations
-----------

- One ``base_url`` per cassette. To record several APIs, open one cassette
  for each (they can be open at the same time).
- The local server speaks plain HTTP. The upstream ``base_url`` can be
  ``https``.
- Responses are buffered completely before they're recorded and replayed:
  streaming responses (server-sent events, long downloads) arrive all at
  once, and WebSockets aren't supported.
- A server-mode cassette opened inside a patch-mode cassette works, but the
  outer cassette records your client's requests to the local server.
