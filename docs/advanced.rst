Advanced Features
=================

If you want, VCR.py can return information about the cassette it is
using to record your requests and responses. This will let you record
your requests and responses and make assertions on them, to make sure
that your code under test is generating the expected requests and
responses. This feature is not present in Ruby's VCR, but I think it is
a nice addition. Here's an example:

.. code:: python

    import vcr
    import urllib.request

    with vcr.use_cassette('fixtures/vcr_cassettes/synopsis.yaml') as cass:
        response = urllib.request.urlopen('http://www.zombo.com/').read()
        # cass should have 1 request inside it
        assert len(cass) == 1
        # the request uri should have been http://www.zombo.com/
        assert cass.requests[0].uri == 'http://www.zombo.com/'

The ``Cassette`` object exposes the following properties which I
consider part of the API. The fields are as follows:

-  ``requests``: A list of vcr.Request objects corresponding to the http
   requests that were made during the recording of the cassette. The
   requests appear in the order that they were originally processed.
-  ``responses``: A list of the responses made.
-  ``play_count``: The number of times this cassette has played back a
   response.
-  ``all_played``: A boolean indicating whether all the responses have
   been played back.
-  ``responses_of(request)``: Access the responses that match a given
   request
-  ``allow_playback_repeats``: A boolean indicating whether responses
   can be played back more than once.

The ``Request`` object has the following properties:

-  ``uri``: The full uri of the request. Example:
   "https://google.com/?q=vcrpy"
-  ``scheme``: The scheme used to make the request (http or https)
-  ``host``: The host of the request, for example "www.google.com"
-  ``port``: The port the request was made on
-  ``path``: The path of the request. For example "/" or "/home.html"
-  ``query``: The parsed query string of the request. Sorted list of
   name, value pairs.
-  ``method`` : The method used to make the request, for example "GET"
   or "POST"
-  ``body``: The body of the request, usually empty except for POST /
   PUT / etc

Backwards compatible properties:

-  ``url``: The ``uri`` alias
-  ``protocol``: The ``scheme`` alias

Register your own serializer
----------------------------

Don't like JSON or YAML? That's OK, VCR.py can serialize to any format
you would like. Create your own module or class instance with 2 methods:

-  ``def deserialize(cassette_string)``
-  ``def serialize(cassette_dict)``

Finally, register your class with VCR to use your new serializer.

.. code:: python

    import vcr

    class BogoSerializer:
        """
        Must implement serialize() and deserialize() methods
        """
        pass

    my_vcr = vcr.VCR()
    my_vcr.register_serializer('bogo', BogoSerializer())

    with my_vcr.use_cassette('test.bogo', serializer='bogo'):
        # your http here

    # After you register, you can set the default serializer to your new serializer

    my_vcr.serializer = 'bogo'

    with my_vcr.use_cassette('test.bogo'):
        # your http here

Cassettes containing custom Python objects
------------------------------------------

For security, VCR.py loads YAML cassettes with a *safe* loader that refuses
the ``!!python/object`` family of tags (loading them could execute arbitrary
code from an untrusted cassette), and it refuses to *record* a cassette
containing such a tag so you find out at record time rather than on replay.

If your requests or responses legitimately contain a custom Python object
(say, a custom ``str`` subclass used as a header value), build a serializer
that knows how to construct that object's tag and register it on your VCR
instance:

.. code:: python

    import vcr
    from vcr.serializers import yamlserializer

    def construct_my_header(loader, node):
        return MyHeader(loader.construct_sequence(node)[0])

    my_vcr = vcr.VCR()
    my_vcr.register_serializer("yaml", yamlserializer.with_custom_tags({
        "tag:yaml.org,2002:python/object/new:myapp.MyHeader": construct_my_header,
    }))

Tags registered this way work symmetrically: the loader can construct them,
so the dumper allows recording them. The default serializer stays locked
down; the custom tags apply only to the VCR instance you registered the
serializer on.

Register your own request matcher
---------------------------------

Create your own method with the following signature

.. code:: python

    def my_matcher(r1, r2):

Your method receives the two requests and can either:

- Use an ``assert`` statement: return None if they match and raise ``AssertionError`` if not.
- Return a boolean: ``True`` if they match, ``False`` if not.

Note: in order to have good feedback when a matcher fails, we recommend using an ``assert`` statement with a clear error message.

Finally, register your method with VCR to use your new request matcher.

.. code:: python

    import vcr

    def jurassic_matcher(r1, r2):
        assert r1.uri == r2.uri and 'JURASSIC PARK' in r1.body, \
            'required string (JURASSIC PARK) not found in request body'

    my_vcr = vcr.VCR()
    my_vcr.register_matcher('jurassic', jurassic_matcher)

    with my_vcr.use_cassette('test.yml', match_on=['jurassic']):
        # your http here

    # After you register, you can set the default match_on to use your new matcher

    my_vcr.match_on = ['jurassic']

    with my_vcr.use_cassette('test.yml'):
        # your http here

Register your own cassette persister
------------------------------------

Create your own persistence class, see the example below:

Your custom persister must implement both ``load_cassette`` and ``save_cassette``
methods.  The ``load_cassette`` method must return a deserialized cassette or raise
either ``CassetteNotFoundError`` if no cassette is found, or ``CassetteDecodeError``
if the cassette cannot be successfully deserialized.

Once the persister class is defined, register with VCR like so...

.. code:: python

    import vcr
    my_vcr = vcr.VCR()

    class CustomerPersister:
        # implement Persister methods...

    my_vcr.register_persister(CustomPersister)

You can also use a persister for a single cassette::

    with my_vcr.use_cassette('fixtures/vcr_cassettes/synopsis.yaml', persister=CustomPersister):
        ...

Filter sensitive data from the request
--------------------------------------

If you are checking your cassettes into source control, and are using
some form of authentication in your tests, you can filter out that
information so it won't appear in your cassette files. There are a few
ways to do this:

Replace secrets with placeholders
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the ``filter_sensitive_data`` configuration option to replace a
secret with a placeholder wherever it appears in a recorded interaction:
the URL, headers, and request and response bodies.

.. code:: python

    import os

    my_vcr = vcr.VCR(
        filter_sensitive_data={"<API_KEY>": os.environ.get("API_KEY", "fake-api-key")},
    )

The cassette file only ever contains ``<API_KEY>``. When the cassette is
loaded, the placeholder is replaced with the value again, so:

- requests made with the real value still match the recorded ones, and
- your code gets the same responses whether they are recorded or played
  back, including any part of a response that contained the secret.

The value can also be a function that's called with the request and
response of each interaction and returns the value to replace, or
``None`` to leave that interaction alone. Values that aren't strings,
like a port number, are matched as text. Values that are empty or
``None`` are skipped, so in CI, where the real secret isn't set, give the
same fallback value to your code and to ``filter_sensitive_data`` (like
``"fake-api-key"`` above) so requests still match.

A few things to keep in mind:

- The replacement is plain text, so a value that is encoded differently
  in part of the interaction (e.g. URL-encoded in a query string, or
  escaped in JSON) needs its own entry with that encoded form.
- Compressed response bodies are stored compressed unless you also set
  ``decode_compressed_response=True``, so a secret inside one isn't found.
- Choose placeholders and values that don't occur in the interactions by
  chance; very short values could replace unrelated text.

Filter information from HTTP Headers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the ``filter_headers`` configuration option with a list of headers
to filter.

.. code:: python

    with my_vcr.use_cassette('test.yml', filter_headers=['authorization']):
        # sensitive HTTP request goes here

Filter information from HTTP querystring
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the ``filter_query_parameters`` configuration option with a list of
query parameters to filter.

.. code:: python

    with my_vcr.use_cassette('test.yml', filter_query_parameters=['api_key']):
        requests.get('http://api.com/getdata?api_key=secretstring')

Filter information from HTTP post data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use the ``filter_post_data_parameters`` configuration option with a list
of post data parameters to filter.

.. code:: python

    with my_vcr.use_cassette('test.yml', filter_post_data_parameters=['api_key']):
        requests.post('http://api.com/postdata', data={'api_key': 'secretstring'})

In JSON bodies, only top-level keys are filtered by default. Set
``filter_nested_post_data_parameters=True`` to also filter keys in nested
objects, including objects in lists, e.g. for request bodies wrapped in an
envelope like JSON-RPC's:

.. code:: python

    my_vcr = VCR(filter_post_data_parameters=['password'], filter_nested_post_data_parameters=True)
    with my_vcr.use_cassette('test.yml'):
        # Recorded as {"method": "login", "params": {"credentials": {"login": "name"}}}
        requests.post('http://api.com/rpc', json={
            'method': 'login',
            'params': {'credentials': {'login': 'name', 'password': 'secret'}},
        })

This filters every key with that name, wherever it is, so make sure the
request doesn't use the same name for something that should be recorded.

Advanced use of filter_headers, filter_query_parameters and filter_post_data_parameters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In all of the above cases, it's also possible to pass a list of ``(key, value)``
tuples where the value can be any of the following:

* A new value to replace the original value.
* ``None`` to remove the key/value pair. (Same as passing a simple key string.)
* A callable that returns a new value or ``None``.

So these two calls are the same:

.. code:: python

    # original (still works)
    vcr = VCR(filter_headers=['authorization'])

    # new
    vcr = VCR(filter_headers=[('authorization', None)])

Here are two examples of the new functionality:

.. code:: python

    # replace with a static value (most common)
    vcr = VCR(filter_headers=[('authorization', 'XXXXXX')])

    # replace with a callable, for example when testing
    # lots of different kinds of authorization.
    def replace_auth(key, value, request):
        auth_type = value.split(' ', 1)[0]
        return '{} {}'.format(auth_type, 'XXXXXX')

Custom Request filtering
~~~~~~~~~~~~~~~~~~~~~~~~

If none of these covers your request filtering needs, you can register a
callback with the ``before_record_request`` configuration option to
manipulate the HTTP request before adding it to the cassette, or return
``None`` to ignore it entirely. Here is an example that will never record
requests to the ``'/login'`` path:

.. code:: python

    def before_record_cb(request):
        if request.path == '/login':
            return None
        return request

    my_vcr = vcr.VCR(
        before_record_request=before_record_cb,
    )
    with my_vcr.use_cassette('test.yml'):
        # your http code here

You can also mutate the request using this callback. For example, you
could remove all query parameters from any requests to the ``'/login'``
path.

.. code:: python

    def scrub_login_request(request):
        if request.path == '/login':
            request.uri = request.uri.split('?', 1)[0]
        return request

    my_vcr = vcr.VCR(
        before_record_request=scrub_login_request,
    )
    with my_vcr.use_cassette('test.yml'):
        # your http code here

Custom Response Filtering
~~~~~~~~~~~~~~~~~~~~~~~~~

You can also do response filtering with the
``before_record_response`` configuration option. Its usage is
similar to the above ``before_record_request`` - you can
mutate the response, or return ``None`` to avoid recording
the request and response altogether. For example to hide
sensitive data from the response body:

.. code:: python

    def scrub_string(string, replacement=''):
        def before_record_response(response):
            response['body']['string'] = response['body']['string'].replace(string, replacement)
            return response
        return before_record_response

    my_vcr = vcr.VCR(
        before_record_response=scrub_string(settings.USERNAME, 'username'),
    )
    with my_vcr.use_cassette('test.yml'):
         # your http code here

.. note::

    The callback is invoked not only when new responses are
    recorded, but also every time an existing cassette is loaded
    for replay: each stored interaction is passed through the
    callback while the cassette is read from disk, even if no
    requests are made afterwards.

    As a result, keep the callback idempotent. When a cassette
    is loaded, the stored responses have already been filtered once
    during the original recording, so the callback runs against
    already-filtered data during replay.

    To filter only what's written to the cassette file, exactly once
    per interaction, use the save and load hooks below instead.

Save and load hooks
~~~~~~~~~~~~~~~~~~~

Two options let you change interactions as a cassette file is written
and read:

- ``before_save_interaction`` runs on each interaction when the cassette
  is saved.
- ``after_load_interaction`` runs on each interaction when the cassette is
  loaded.

Each hook is called with an interaction's request and response, and
returns them, changed or not, or ``None`` to leave the interaction out:
out of the saved file, or out of the interactions that can be played
back.

When to use them
^^^^^^^^^^^^^^^^

**To change a response based on its request.** ``before_record_response``
only sees the response, so it can't tell which endpoint it came from.
For example, to keep a login request in the cassette but scrub the token
from its response:

.. code:: python

    import re

    def scrub_login_token(request, response):
        if request.path == '/login':
            response['body']['string'] = re.sub(
                rb'"token": "[^"]*"', b'"token": "<TOKEN>"', response['body']['string']
            )
        return request, response

    my_vcr = vcr.VCR(before_save_interaction=scrub_login_token)

**To keep cookies out of cassettes.** ``filter_headers`` only filters
request headers. A save hook can drop both ``Cookie`` and ``Set-Cookie``
(your code won't get those cookies when the cassette is played back):

.. code:: python

    def drop_cookies(request, response):
        request.headers.pop('Cookie', None)
        response['headers'] = {
            name: values for name, values in response['headers'].items() if name.lower() != 'set-cookie'
        }
        return request, response

**To filter only what's written to the file, exactly once.**
``before_record_request`` also runs on every request before it's matched
against the cassette, and both it and ``before_record_response`` run again
on interactions loaded from a cassette, so they need to be safe to run
more than once. Save and load hooks run once per interaction.

**To replay part of a cassette and record the rest again.** A load hook
that leaves interactions out, with the ``new_episodes`` record mode,
replays the interactions it keeps and records the others again. For
example, to replay only the first two:

.. code:: python

    import itertools

    def keep_first(n):
        loaded = itertools.count()

        def hook(request, response):
            return (request, response) if next(loaded) < n else None

        return hook

    with vcr.use_cassette('debug.yaml', record_mode='new_episodes', after_load_interaction=keep_first(2)):
        ...

**To use old cassettes after something changed.** If an API moved, or an
upgrade changed how a URL is recorded, a load hook can rewrite the
recorded requests so they match again, without re-recording:

.. code:: python

    def use_v2_urls(request, response):
        request.uri = request.uri.replace('/v1/', '/v2/')
        return request, response

**To keep secrets out of cassettes.** Use ``filter_sensitive_data`` (see
above), which is built on these hooks.

Details
^^^^^^^

- Each option takes one function or a list of them, applied in order.
- Save hooks get copies, so they don't change the requests and responses
  your code sees while recording.
- A hook that takes a third argument is also given the cassette, e.g. to
  only change the interactions of some cassettes:

  .. code:: python

      def drop_health_checks(request, response, cassette):
          if 'smoke_tests' in cassette.path and request.path == '/health':
              return None
          return request, response

- ``filter_sensitive_data`` replaces values after your save hooks run and
  restores them before your load hooks run, so your hooks always see the
  real values, and a secret can't end up in the cassette file even if a
  save hook copies it somewhere. This is the opposite order from
  ``before_record_request`` and ``before_record_response``, which run
  after the built-in filters (like ``filter_headers`` and
  ``decode_compressed_response``) and so see already-filtered requests and
  responses.


Decode compressed response
---------------------------

When the ``decode_compressed_response`` keyword argument of a ``VCR`` object
is set to True, VCR will decompress "gzip" and "deflate" response bodies
before recording. This ensures that these interactions become readable and
editable after being serialized.

.. note::
    Decompression is done before any other specified `Custom Response Filtering`_.

This option should be avoided if the actual decompression of response bodies
is part of the functionality of the library or app being tested.

Ignore requests
---------------

If you would like to completely ignore certain requests, you can do it
in a few ways:

-  Set the ``ignore_localhost`` option equal to True. This will not
   record any requests sent to (or responses from) localhost, 127.0.0.1,
   ::1 or 0.0.0.0.
-  Set the ``ignore_hosts`` configuration option to a list of hosts to
   ignore. A host can also be a compiled regular expression, which has to
   match the whole host name, e.g.
   ``ignore_hosts=["example.com", re.compile(r".*\.actions\.githubusercontent\.com")]``
-  Add a ``before_record_request`` or ``before_record_response`` callback
   that returns ``None`` for requests you want to ignore (see above).

Requests that are ignored by VCR will not be saved in a cassette, nor
played back from a cassette. VCR will completely ignore those requests
as if it didn't notice them at all, and they will continue to hit the
server as if VCR were not there.

Custom Patches
--------------

If you use a custom ``HTTPConnection`` class, or otherwise make http
requests in a way that requires additional patching, you can use the
``custom_patches`` keyword argument of the ``VCR`` and ``Cassette``
objects to patch those objects whenever a cassette's context is entered.
To patch a custom version of ``HTTPConnection`` you can do something
like this:

::

    import where_the_custom_https_connection_lives
    from vcr.stubs import VCRHTTPSConnection
    my_vcr = config.VCR(custom_patches=((where_the_custom_https_connection_lives, 'CustomHTTPSConnection', VCRHTTPSConnection),))

    @my_vcr.use_cassette(...)

Skipping Patchers
-----------------

VCR.py patches every HTTP library it supports while a cassette is in use.
If one library sends its requests through another, e.g. an httpx client
using an aiohttp transport (httpx-aiohttp), each request would be recorded
twice, once by each patcher. The ``skip_patchers`` option of ``VCR`` and
``use_cassette`` leaves the named libraries unpatched, so the request is
recorded only by the library underneath:

.. code:: python

    my_vcr = vcr.VCR(skip_patchers=["httpx"])

The names are ``httplib``, ``requests``, ``boto3``, ``urllib3``,
``httplib2``, ``tornado``, ``aiohttp``, ``httpx`` and ``httpx2``, also
available as ``vcr.patch.PATCHER_NAMES``. Requests made through a skipped
library aren't recorded or played back unless another patched library
handles them, so e.g. ``skip_patchers=["httpx"]`` stops recording httpx's
default transport.

Automatic Cassette Naming
-------------------------

VCR.py now allows the omission of the path argument to the use\_cassette
function. Both of the following are now legal/should work

.. code:: python

    @my_vcr.use_cassette
    def my_test_function():
        ...

.. code:: python

    @my_vcr.use_cassette()
    def my_test_function():
        ...

In both cases, VCR.py will use a path that is generated from the
provided test function's name. If no ``cassette_library_dir`` has been
set, the cassette will be in a file with the name of the test function
in directory of the file in which the test function is declared. If a
``cassette_library_dir`` has been set, the cassette will appear in that
directory in a file with the name of the decorated function.

It is possible to control the path produced by the automatic naming
machinery by customizing the ``path_transformer`` and
``func_path_generator`` vcr variables. To add an extension to all
cassette names, use ``VCR.ensure_suffix`` as follows:

.. code:: python

    my_vcr = VCR(path_transformer=VCR.ensure_suffix('.yaml'))

    @my_vcr.use_cassette
    def my_test_function():

Rewind Cassette
---------------

VCR.py allows to rewind a cassette in order to replay it inside the same function/test.

.. code:: python

    import vcr
    import urllib.request

    with vcr.use_cassette('fixtures/vcr_cassettes/synopsis.yaml') as cass:
        response = urllib.request.urlopen('http://www.zombo.com/').read()
        assert cass.all_played
        cass.rewind()
        assert not cass.all_played

Playback Repeats
----------------

By default, each response in a cassette can only be matched and played back
once while the cassette is in use, unless the cassette is rewound.

If you want to allow playback repeats without rewinding the cassette, use
the Cassette ``allow_playback_repeats`` option. It also applies while
recording: once a request has been recorded, matching requests get the
recorded response instead of being sent and recorded again.

.. code:: python

    import vcr
    import urllib.request

    with vcr.use_cassette('fixtures/vcr_cassettes/synopsis.yaml', allow_playback_repeats=True) as cass:
        for x in range(10):
            response = urllib.request.urlopen('http://www.zombo.com/').read()
        assert cass.all_played

Discards Cassette on Errors
---------------------------

By default VCR will save the cassette file even when there is any error inside
the enclosing context/test.

If you want to save the cassette only when the test succeeds, set the Cassette
``record_on_exception`` option to ``False``.

.. code:: python

    import os
    import urllib.request
    import vcr

    try:
        my_vcr = vcr.VCR(record_on_exception=False)
        with my_vcr.use_cassette('fixtures/vcr_cassettes/synopsis.yaml') as cass:
            response = urllib.request.urlopen('http://www.zombo.com/').read()
            raise RuntimeError("Oops, something happened")
    except RuntimeError:
        pass

    # Since there was an exception, the cassette file hasn't been created.
    assert not os.path.exists('fixtures/vcr_cassettes/synopsis.yaml')

Drop unused requests
--------------------

Even if any HTTP request is changed or removed from tests, previously recorded
interactions remain in the cassette file.  If set the ``drop_unused_requests``
option to ``True``, VCR will not save old HTTP interactions if they are not used.

.. code:: python

    my_vcr = VCR(drop_unused_requests=True)
    with my_vcr.use_cassette('fixtures/vcr_cassettes/synopsis.yaml'):
        ...  # your HTTP interactions here

Cassette Metadata
-----------------

Sometimes a test needs values that aren't part of any interaction, but
have to be the same when it's recorded and when it's played back: e.g. a
random ID the test sends in its requests, or a value it got from outside
VCR.py, such as a browser redirect. ``cassette.get_metadata(key, default)``
stores such values in the cassette. It returns the value the cassette has
for ``key``; if it has none, it stores ``default`` and returns it.

.. code:: python

    import random
    import uuid

    with my_vcr.use_cassette('fixtures/vcr_cassettes/synopsis.yaml') as cass:
        # A new seed when the cassette is recorded, the recorded seed when it's played back
        seed = cass.get_metadata("seed", random.getrandbits(128))
        rng = random.Random(seed)
        order_id = uuid.UUID(int=rng.getrandbits(128), version=4)
        ...  # your HTTP interactions here, using order_id

The values are saved under ``metadata`` in the cassette file, so they have
to be serializable, e.g. strings, numbers, lists and dicts. If the cassette
has no value for ``key`` and the record mode doesn't allow changing it, e.g.
``once`` with an existing cassette, ``get_metadata`` raises
``vcr.errors.MissingMetadataError``, a ``CannotOverwriteExistingCassetteException``.
