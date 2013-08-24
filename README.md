#VCR.py

![vcr.py](https://raw.github.com/kevin1024/vcrpy/master/vcr.png)

This is a Python version of [Ruby's VCR library](https://github.com/myronmarston/vcr).

[![Build Status](https://secure.travis-ci.org/kevin1024/vcrpy.png?branch=master)](http://travis-ci.org/kevin1024/vcrpy)

##What it does
Simplify and speed up testing HTTP by recording all HTTP interactions and saving them to
"cassette" files, which are yaml files containing the contents of your
requests and responses.  Then when you run your tests again, they all 
just hit the text files instead of the internet.  This speeds up
your tests and lets you work offline.

If the server you are testing against ever changes its API, all you need
to do is delete your existing cassette files, and run your tests again.
All of the mocked responses will be updated with the new API.

##Compatibility Notes
This should work with Python 2.6 and 2.7, and [pypy](http://pypy.org).

Currently I've only tested this with urllib2, urllib3, and requests.  It's known to *NOT WORK* with urllib.

##How to use it
```python
import vcr
import urllib2

with vcr.use_cassette('fixtures/vcr_cassettes/synopsis.yaml'):
    response = urllib2.urlopen('http://www.iana.org/domains/reserved').read()
    assert 'Example domains' in response
```

Run this test once, and VCR.py will record the http request to
`fixtures/vcr_cassettes/synopsis.yml`. Run it again, and VCR.py will replay the
response from iana.org when the http request is made. This test is now fast (no
real HTTP requests are made anymore), deterministic (the test will continue to
pass, even if you are offline, or iana.org goes down for maintenance) and
accurate (the response will contain the same headers and body you get from a
real request).

## Configuration

If you don't like VCR's defaults, you can set options by instantiating a
VCR class and setting the options on it.

```python

import vcr

my_vcr = vcr.VCR(
    serializer = 'json',
    cassette_library_dir = 'fixtures/cassettes',
)

with my_vcr.use_cassette('test.json'):
    # your http code here
```

Otherwise, you can override options each time you use a cassette.  

```python
with vcr.use_cassette('test.yml', serializer='json'):
    # your http code here
```

Note: Per-cassette overrides take precedence over the global config.

## Advanced Features

If you want, VCR.py can return information about the cassette it is
using to record your requests and responses.  This will let you record
your requests and responses and make assertions on them, to make sure
that your code under test is generating the expected requests and
responses.  This feature is not present in Ruby's VCR, but I think it is
a nice addition.  Here's an example:

```python
import vcr
import urllib2

with vcr.use_cassette('fixtures/vcr_cassettes/synopsis.yaml') as cass:
    response = urllib2.urlopen('http://www.zombo.com/').read()
    # cass should have 1 request inside it
    assert len(cass) == 1 
    # the request url should have been http://www.zombo.com/
    assert cass.requests[0].url == 'http://www.zombo.com/'
```

The Cassette object exposes the following properties which I consider
part of the API.  The fields are as follows:

* `requests`: A list of vcr.Request objects containing the requests made
  while this cassette was being used, ordered by the order that the
  request was made.
* `responses`: A list of the responses made.
* `play_count`: The number of times this cassette has had a response
  played back
* `play_counts`: A collections.Counter showing the number of times each
  response has been played back, indexed by the request
* `response_of(request)`: Access the response for a given request.

The Request object has the following properties

  * `URL`: The full url of the request, including the protocol.  Example: "http://www.google.com/"
  * `path`: The path of the request.  For example "/" or "/home.html"
  * `host`: The host of the request, for example "www.google.com"
  * `port`: The port the request was made on
  * `method` : The method used to make the request, for example "GET" or "POST"
  * `protocol`: The protocol used to make the request (http or https)
  * `body`: The body of the request, usually empty except for POST / PUT / etc

## Register your own serializer

Don't like JSON or YAML?  That's OK, VCR.py can serialize to any format
you would like.  Create your own module or class instance with 2 methods:

 * `def deserialize(cassette_string)`
 * `def serialize(cassette_dict)`

Finally, register your class with VCR to use your
new serializer.

```
import vcr

BogoSerializer(object):
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

```

##Installation

VCR.py is a package on PyPI, so you can `pip install vcrpy` (first you may need to `brew install libyaml` [[Homebrew](http://mxcl.github.com/homebrew/)])

##Ruby VCR compatibility
I'm not trying to match the format of the Ruby VCR YAML files.  Cassettes generated by
Ruby's VCR are not compatible with VCR.py.

##Known Issues
This library is a work in progress, so the API might change on you.
There are probably some [bugs](https://github.com/kevin1024/vcrpy/issues?labels=bug&page=1&state=open) floating around too.

##Changelog
* 0.2.0: Added configuration API, which lets you configure some settings
  on VCR (see the README). Also, VCR no longer saves cassettes if they
  haven't changed at all and supports JSON as well as YAML 
  (thanks @sirpengi)
* 0.1.0: *backwards incompatible release - delete your old cassette files*:  
  This release adds the ability to access the cassette to make assertions 
  on it, as well as a major code refactor thanks to @dlecocq.  It also
  fixes a couple longstanding bugs with redirects and HTTPS. [#3 and #4]
* 0.0.4: If you have libyaml installed, vcrpy will use the c bindings
  instead.  Speed up your tests!  Thanks @dlecocq
* 0.0.3: Add support for requests 1.2.3.  Support for older versions of requests dropped (thanks @vitormazzi and @bryanhelmig)
* 0.0.2: Add support for requests / urllib3
* 0.0.1: Initial Release

##Similar libraries in Python
Neither of these really implement the API I want, but I have cribbed some code
from them.
 * https://github.com/bbangert/Dalton
 * https://github.com/storborg/replaylib

These were created after I created VCR.py but do something similar:

 * https://github.com/gabrielfalcao/HTTPretty
 * https://github.com/kanzure/python-requestions
 * https://github.com/uber/cassette

#License
This library uses the MIT license.  See [LICENSE.txt](LICENSE.txt) for more details
