
###########
VCR.py 📼
###########


|PyPI| |Python versions| |Build Status| |CodeCov| |Gitter|

----

.. image:: https://vcrpy.readthedocs.io/en/latest/_images/vcr.svg
   :alt: vcr.py logo


This is a Python version of `Ruby's VCR
library <https://github.com/vcr/vcr>`__.

Source code
  https://github.com/kevin1024/vcrpy

Documentation
  https://vcrpy.readthedocs.io/

Rationale
---------

VCR.py simplifies and speeds up tests that make HTTP requests. The
first time you run code that is inside a VCR.py context manager or
decorated function, VCR.py records all HTTP interactions that take
place through the libraries it supports and serializes and writes them
to a flat file (in yaml format by default). This flat file is called a
cassette. When the relevant piece of code is executed again, VCR.py
will read the serialized requests and responses from the
aforementioned cassette file, and intercept any HTTP requests that it
recognizes from the original test run and return the responses that
corresponded to those requests. This means that the requests will not
actually result in HTTP traffic, which confers several benefits
including:

-  The ability to work offline
-  Completely deterministic tests
-  Increased test execution speed

If the server you are testing against ever changes its API, all you need
to do is delete your existing cassette files, and run your tests again.
VCR.py will detect the absence of a cassette file and once again record
all HTTP interactions, which will update them to correspond to the new
API.

Usage with Pytest
-----------------

There is a library to provide some pytest fixtures called pytest-recording https://github.com/kiwicom/pytest-recording

License
-------

This library uses the MIT license. See `LICENSE.txt <LICENSE.txt>`__ for
more details

.. |PyPI| image:: https://img.shields.io/pypi/v/vcrpy.svg
   :target: https://pypi.python.org/pypi/vcrpy
.. |Python versions| image:: https://img.shields.io/pypi/pyversions/vcrpy.svg
   :target: https://pypi.python.org/pypi/vcrpy
.. |Build Status| image:: https://github.com/kevin1024/vcrpy/actions/workflows/main.yml/badge.svg
   :target: https://github.com/kevin1024/vcrpy/actions
.. |Gitter| image:: https://badges.gitter.im/Join%20Chat.svg
   :alt: Join the chat at https://gitter.im/kevin1024/vcrpy
   :target: https://gitter.im/kevin1024/vcrpy?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge
.. |CodeCov| image:: https://codecov.io/gh/kevin1024/vcrpy/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/kevin1024/vcrpy
   :alt: Code Coverage Status
