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
