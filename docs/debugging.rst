Debugging
=========

VCR.py has a few log messages you can turn on to help you figure out if
HTTP requests are hitting a real server or not. You can turn them on
like this:

.. code:: python

    import vcr
    import requests
    import logging

    logging.basicConfig() # you need to initialize logging, otherwise you will not see anything from vcrpy
    vcr_log = logging.getLogger("vcr")
    vcr_log.setLevel(logging.INFO)

    with vcr.use_cassette('headers.yml'):
        requests.get('http://httpbin.org/headers')

The first time you run this, you will see::

    INFO:vcr.stubs:<Request (GET) http://httpbin.org/headers> not in cassette, sending to real server

The second time, you will see::

    INFO:vcr.stubs:Playing response for <Request (GET) http://httpbin.org/headers> from cassette

If you set the loglevel to DEBUG, you will also get information about
which matchers didn't match. This can help you with debugging custom
matchers.

CannotOverwriteExistingCassetteException
----------------------------------------

When a request failed to be found in an existing cassette,
VCR.py tries to get the request(s) that may be similar to the one being searched.
The goal is to see which matcher(s) failed and understand what part of the failed request may have changed.
It can return multiple similar requests with :

- the matchers that have succeeded
- the matchers that have failed
- for each failed matchers, why it has failed with an assertion message

CannotOverwriteExistingCassetteException message example :

.. code::

    CannotOverwriteExistingCassetteException: Can't overwrite existing cassette ('cassette.yaml') in your current record mode ('once').
    No match for the request (<Request (GET) https://www.googleapis.com/?alt=json&maxResults=200>) was found.
    Found 1 similar requests with 1 different matchers :

    1 - (<Request (GET) https://www.googleapis.com/?alt=json&maxResults=500>).
    Matchers succeeded : ['method', 'scheme', 'host', 'port', 'path']
    Matchers failed :
    query - assertion failure :
    [('alt', 'json'), ('maxResults', '200')] != [('alt', 'json'), ('maxResults', '500')]
