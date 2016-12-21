Command-line tool
=================

You can inspect and modify recorded cassettes using command line tool.


Editing request and response bodies
-----------------------------------

Large request or response bodies usually are not very conveniet to edit
directly in YAML or JSON file. Using ``vcr`` command line tool you can edit
request/response bodies much easier.

In order to do that, first you need to pick a track to edit from your
cassette::

    $ vcr path/to/cassette.yml
      0   GET https://httpbin.org/xml
      1   GET https://httpbin.org/xml

From this output you can see number of each track. Then to edit response of
track ``1`` you need to run this command::

    $ vcr path/to/cassette.yml 1 -e response

This command will open your favorite editor (specified in ``EDITOR``
environment variable) with content of track ``1`` response body. Modify
response body as you like, save changes and close editor. Cassette will be
updated with you changes.
