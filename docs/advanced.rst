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
    import urllib2

    with vcr.use_cassette('fixtures/vcr_cassettes/synopsis.yaml') as cass:
        response = urllib2.urlopen('http://www.zombo.com/').read()
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

    class BogoSerializer(object):
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
``ValueError`` if no cassette is found.

Once the persister class is defined, register with VCR like so...

.. code:: python

    import vcr
    my_vcr = vcr.VCR()

    class CustomerPersister:
        # implement Persister methods...

    my_vcr.register_persister(CustomPersister)

Filter sensitive data from the request
--------------------------------------

If you are checking your cassettes into source control, and are using
some form of authentication in your tests, you can filter out that
information so it won't appear in your cassette files. There are a few
ways to do this:

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

    with my_vcr.use_cassette('test.yml', filter_post_data_parameters=['client_secret']):
        requests.post('http://api.com/postdata', data={'api_key': 'secretstring'})

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
            request.uri, _ =  urllib.splitquery(request.uri)
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
sensitive data from the request body:

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
   or 0.0.0.0.
-  Set the ``ignore_hosts`` configuration option to a list of hosts to
   ignore
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

    with vcr.use_cassette('fixtures/vcr_cassettes/synopsis.yaml') as cass:
        response = urllib2.urlopen('http://www.zombo.com/').read()
        assert cass.all_played
        cass.rewind()
        assert not cass.all_played

Playback Repeats
----------------

By default, each response in a cassette can only be matched and played back
once while the cassette is in use, unless the cassette is rewound.

If you want to allow playback repeats without rewinding the cassette, use
the Cassette ``allow_playback_repeats`` option.

.. code:: python

    with vcr.use_cassette('fixtures/vcr_cassettes/synopsis.yaml', allow_playback_repeats=True) as cass:
        for x in range(10):
            response = urllib2.urlopen('http://www.zombo.com/').read()
        assert cass.all_played
