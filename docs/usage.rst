Usage
=====

.. code:: python

    import vcr
    import urllib

    with vcr.use_cassette('fixtures/vcr_cassettes/synopsis.yaml'):
        response = urllib.request.urlopen('http://www.iana.org/domains/reserved').read()
        assert 'Example domains' in response

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
        assert 'Example domains' in response

When using the decorator version of ``use_cassette``, it is possible to
omit the path to the cassette file.

.. code:: python

    @vcr.use_cassette()
    def test_iana():
        response = urllib.request.urlopen('http://www.iana.org/domains/reserved').read()
        assert 'Example domains' in response

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

While it's possible to use the context manager or decorator forms with unittest,
there's also a ``VCRTestCase`` provided separately by `vcrpy-unittest
<https://github.com/agriffis/vcrpy-unittest>`__.

Pytest Integration
------------------

A Pytest plugin is available here : `pytest-vcr
<https://github.com/ktosiek/pytest-vcr>`__.

Alternative plugin, that also provides network access blocking: `pytest-recording
<https://github.com/kiwicom/pytest-recording>`__.
