Contributing
============

Running VCR's test suite
------------------------

The tests are all run automatically on `Travis
CI <https://travis-ci.org/kevin1024/vcrpy>`__, but you can also run them
yourself using `py.test <http://pytest.org/>`__ and
`Tox <http://tox.testrun.org/>`__. Tox will automatically run them in
all environments VCR.py supports. The test suite is pretty big and slow,
but you can tell tox to only run specific tests like this::

    tox -e {pyNN}-{HTTP_LIBRARY} -- <pytest flags passed through>

    tox -e py27-requests -- -v -k "'test_status_code or test_gzip'"
    tox -e py37-requests -- -v --last-failed

This will run only tests that look like ``test_status_code`` or
``test_gzip`` in the test suite, and only in the python 2.7 environment
that has ``requests`` installed.

Also, in order for the boto tests to run, you will need an AWS key.
Refer to the `boto
documentation <https://boto.readthedocs.io/en/latest/getting_started.html>`__
for how to set this up. I have marked the boto tests as optional in
Travis so you don't have to worry about them failing if you submit a
pull request.


Troubleshooting on MacOSX
-------------------------

If you have this kind of error when running tox :

.. code:: python

    __main__.ConfigurationError: Curl is configured to use SSL, but we have
    not been able to determine which SSL backend it is using. Please see PycURL documentation for how to specify the SSL backend manually.

Then you need to define some environment variables:

.. code:: bash

    export PYCURL_SSL_LIBRARY=openssl
    export LDFLAGS=-L/usr/local/opt/openssl/lib
    export CPPFLAGS=-I/usr/local/opt/openssl/include

Reference : `stackoverflow issue <https://stackoverflow.com/questions/51019622/curl-is-configured-to-use-ssl-but-we-have-not-been-able-to-determine-which-ssl>`__
