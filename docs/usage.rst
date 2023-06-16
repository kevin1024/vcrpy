Usage
=====

.. code:: python

    import vcr
    import urllib.request

    with vcr.use_cassette('fixtures/vcr_cassettes/synopsis.yaml'):
        response = urllib.request.urlopen('http://www.iana.org/domains/reserved').read()
        assert b'Example domains' in response

Run this test once, and VCR.py will record the HTTP request to
``fixtures/vcr_cassettes/synopsis.yaml``. Run it again, and VCR.py will
replay the response from iana.org when the http request is made. This
test is now fast (no real HTTP requests are made anymore), deterministic
(the test will continue to pass, even if you are offline, or iana.org
goes down for maintenance) and accurate (the response will contain the
same headers and body you get from a real request).

You can also use VCR.py as a decorator. The same request above would
look like this:

.. code:: python

    @vcr.use_cassette('fixtures/vcr_cassettes/synopsis.yaml')
    def test_iana():
        response = urllib.request.urlopen('http://www.iana.org/domains/reserved').read()
        assert b'Example domains' in response

When using the decorator version of ``use_cassette``, it is possible to
omit the path to the cassette file.

.. code:: python

    @vcr.use_cassette()
    def test_iana():
        response = urllib.request.urlopen('http://www.iana.org/domains/reserved').read()
        assert b'Example domains' in response

In this case, the cassette file will be given the same name as the test
function, and it will be placed in the same directory as the file in
which the test is defined. See the Automatic Test Naming section below
for more details.

Record Modes
------------

VCR supports 4 record modes (with the same behavior as Ruby's VCR):

once
~~~~

-  Replay previously recorded interactions.
-  Record new interactions if there is no cassette file.
-  Cause an error to be raised for new requests if there is a cassette
   file.

It is similar to the new\_episodes record mode, but will prevent new,
unexpected requests from being made (e.g. because the request URI
changed).

once is the default record mode, used when you do not set one.

new\_episodes
~~~~~~~~~~~~~

-  Record new interactions.
-  Replay previously recorded interactions. It is similar to the once
   record mode, but will always record new interactions, even if you
   have an existing recorded one that is similar, but not identical.

This was the default behavior in versions < 0.3.0

none
~~~~

-  Replay previously recorded interactions.
-  Cause an error to be raised for any new requests. This is useful when
   your code makes potentially dangerous HTTP requests. The none record
   mode guarantees that no new HTTP requests will be made.

all
~~~

-  Record new interactions.
-  Never replay previously recorded interactions. This can be
   temporarily used to force VCR to re-record a cassette (i.e. to ensure
   the responses are not out of date) or can be used when you simply
   want to log all HTTP requests.

Unittest Integration
--------------------

Inherit from ``VCRTestCase`` for automatic recording and playback of HTTP
interactions.

.. code:: python

    from vcr.unittest import VCRTestCase
    import requests

    class MyTestCase(VCRTestCase):
       def test_something(self):
           response = requests.get('http://example.com')

Similar to how VCR.py returns the cassette from the context manager,
``VCRTestCase`` makes the cassette available as ``self.cassette``:

.. code:: python

    self.assertEqual(len(self.cassette), 1)
    self.assertEqual(self.cassette.requests[0].uri, 'http://example.com')

By default cassettes will be placed in the ``cassettes`` subdirectory next to the
test, named according to the test class and method. For example, the above test
would read from and write to ``cassettes/MyTestCase.test_something.yaml``

The configuration can be modified by overriding methods on your subclass:
``_get_vcr_kwargs``, ``_get_cassette_library_dir`` and ``_get_cassette_name``.
To modify the ``VCR`` object after instantiation, for example to add a matcher,
you can hook on ``_get_vcr``, for example:

.. code:: python

    class MyTestCase(VCRTestCase):
        def _get_vcr(self, **kwargs):
            myvcr = super(MyTestCase, self)._get_vcr(**kwargs)
            myvcr.register_matcher('mymatcher', mymatcher)
            myvcr.match_on = ['mymatcher']
            return myvcr

See
`the source
<https://github.com/kevin1024/vcrpy/blob/master/vcr/unittest.py>`__
for the default implementations of these methods.

If you implement a ``setUp`` method on your test class then make sure to call
the parent version ``super().setUp()`` in your own in order to continue getting
the cassettes produced.

VCRMixin
~~~~~~~~

In case inheriting from ``VCRTestCase`` is difficult because of an existing
class hierarchy containing tests in the base classes, inherit from ``VCRMixin``
instead.

.. code:: python

    from vcr.unittest import VCRMixin
    import requests
    import unittest

    class MyTestMixin(VCRMixin):
       def test_something(self):
           response = requests.get(self.url)

    class MyTestCase(MyTestMixin, unittest.TestCase):
        url = 'http://example.com'


Pytest Integration
------------------

A Pytest plugin is available here : `pytest-vcr
<https://github.com/ktosiek/pytest-vcr>`__.

Alternative plugin, that also provides network access blocking: `pytest-recording
<https://github.com/kiwicom/pytest-recording>`__.
