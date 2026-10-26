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

VCR.py raises ``CannotOverwriteExistingCassetteException`` when a request
isn't in the cassette and the record mode doesn't allow recording it. The
message starts with what went wrong, then shows the request, the cassette's
settings and, when it helps, the recorded requests closest to the one being
made, with how each of them differs. It ends with suggestions for fixing it.

For example, when the query string of a request changed:

.. code::

    CannotOverwriteExistingCassetteException: Can't play back this request: no recorded interaction matches it (the closest differ in query).
    record_mode 'once' doesn't record new requests into an existing cassette.

      GET https://www.googleapis.com/?alt=json&maxResults=200

    Cassette: cassette.yaml
      record_mode: once
      match_on: method, scheme, host, port, path, query
      interactions: 1 recorded, 0 played

    Closest recorded requests:
      1. GET https://www.googleapis.com/?alt=json&maxResults=500
         query differs: [('alt', 'json'), ('maxResults', '200')] != [('alt', 'json'), ('maxResults', '500')]

    How to fix:
      * If the request changed on purpose, record it again: run once with
        record_mode='new_episodes' to add it to the cassette, or record_mode='all'
        with drop_unused_requests=True to re-record the cassette from scratch [1].
      * If the difference changes on every run (a timestamp, a random ID), make
        matching ignore it: loosen match_on, or normalize the request with
        before_record_request [2].

    [1] https://vcrpy.readthedocs.io/en/latest/usage.html#record-modes
    [2] https://vcrpy.readthedocs.io/en/latest/configuration.html#request-matching

When a request body differs, the message shows a short diff of the bodies.
At most three of the closest recorded requests are shown in full; the rest
are summarized by how they differ.

The exception also has these attributes, for tools that want to report the
problem themselves:

- ``cassette`` and ``failed_request``: the cassette and the request that
  couldn't be handled.
- ``reason``: why it couldn't be handled. ``"cassette_not_found"`` when the
  cassette file doesn't exist (or couldn't be loaded) and the record mode
  can't create it, ``"already_played"`` when the matching recorded
  interactions have all been played back already, ``"no_match"`` when
  recorded requests are similar but none matches, and ``"nothing_similar"``
  when nothing in the cassette is similar.
- ``similar_requests``: the closest recorded requests, as
  ``(request, succeeded_matchers, failed_matchers)`` tuples, where
  ``failed_matchers`` is a list of ``(matcher_name, message)`` tuples.
