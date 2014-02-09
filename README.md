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

##Usage
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

You can also use VCR.py as a decorator.  The same request above would look like this:

```
@vcr.use_cassette('fixtures/vcr_cassettes/synopsis.yaml'):
def test_iana():
    response = urllib2.urlopen('http://www.iana.org/domains/reserved').read()
    assert 'Example domains' in response
```

All of the parameters and configuration works the same for the decorator version.

## Configuration

If you don't like VCR's defaults, you can set options by instantiating a
VCR class and setting the options on it.

```python

import vcr

my_vcr = vcr.VCR(
    serializer = 'json',
    cassette_library_dir = 'fixtures/cassettes',
    record_mode = 'once',
    match_on = ['url', 'method'],
)

with my_vcr.use_cassette('test.json'):
    # your http code here
```

Otherwise, you can override options each time you use a cassette.  

```python
with vcr.use_cassette('test.yml', serializer='json', record_mode='once'):
    # your http code here
```

Note: Per-cassette overrides take precedence over the global config.

## Request matching

Request matching is configurable and allows you to change which requests
VCR considers identical.  The default behavior is `['url', method']`
which means that requests with both the same URL and method (ie POST or
GET) are considered identical.

This can be configured by changing the `match_on` setting.

The following options are available :

 * method (for example, POST or GET)
 * url (the full URL, including the protocol)
 * host (the hostname of the server receiving the request)
 * path (excluding the hostname)
 * body (the entire request body)
 * headers (the headers of the request)

If these options don't work for you, you can also register your own
request matcher.  This is described in the Advanced section of this
README.

## Record Modes
VCR supports 4 record modes (with the same behavior as Ruby's VCR):

### once

 * Replay previously recorded interactions.
 * Record new interactions if there is no cassette file.
 * Cause an error to be raised for new requests if there is a cassette file.
 
It is similar to the new_episodes record mode, but will prevent new,
unexpected requests from being made (i.e. because the request URI
changed).

once is the default record mode, used when you do not set one.

### new_episodes

* Record new interactions.
* Replay previously recorded interactions.
It is similar to the once record mode, but will always record new
interactions, even if you have an existing recorded one that is similar,
but not identical.

This was the default behavior in versions < 0.3.0

### none

* Replay previously recorded interactions.
* Cause an error to be raised for any new requests.
This is useful when your code makes potentially dangerous
HTTP requests. The none record mode guarantees that no
new HTTP requests will be made.

### all

* Record new interactions.
* Never replay previously recorded interactions.
This can be temporarily used to force VCR to re-record
a cassette (i.e. to ensure the responses are not out of date)
or can be used when you simply want to log all HTTP requests.

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
* `responses_of(request)`: Access the responses that match a given request

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

```python
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

## Register your own request matcher

Create your own method with the following signature

```python
def my_matcher(r1, r2):
```    

Your method receives the two requests and must return True if they
match, False if they don't.

Finally, register your method with VCR to use your
new request matcher.

```python
import vcr

def jurassic_matcher(r1, r2):
    return r1.url == r2.url and 'JURASSIC PARK' in r1.body

my_vcr = vcr.VCR()
my_vcr.register_matcher('jurassic', jurassic_matcher)

with my_vcr.use_cassette('test.yml', match_on=['jurassic']):
    # your http here

# After you register, you can set the default match_on to use your new matcher

my_vcr.match_on = ['jurassic']

with my_vcr.use_cassette('test.yml'):
    # your http here

```

##Installation

VCR.py is a package on PyPI, so you can `pip install vcrpy` (first you may need to `brew install libyaml` [[Homebrew](http://mxcl.github.com/homebrew/)])

##Ruby VCR compatibility
I'm not trying to match the format of the Ruby VCR YAML files.  Cassettes generated by
Ruby's VCR are not compatible with VCR.py.

##Running VCR's test suite

The tests are all run automatically on Travis, but you can also run them yourself using py.test and Tox.  Tox will automatically run them in all environments VCR.py supports.  The test suite is pretty big and slow, but you can tell tox to only run specific tests like this:

`tox -e py27requests -- -v -k "'test_status_code or test_gzip'"`

This will run only tests that look like `test_status_code` or `test_gzip` in the test suite, and only in the python 2.7 environment that has requests installed.

##Known Issues
This library is a work in progress, so the API might change on you.
There are probably some [bugs](https://github.com/kevin1024/vcrpy/issues?labels=bug&page=1&state=open) floating around too.

##Changelog
* 0.6.0: Store response headers as a list since a HTTP response can have the same header twice (happens with set-cookie sometimes).  This has the added benefit of preserving the order of headers. Thanks @smallcode for the bug report leading to this change.  I have made an effort to ensure backwards compatibility with the old cassettes' header storage mechanism, but if you want to upgrade to the new header storage, you should delete your cassettes and re-record them.  Also this release adds better error messages (thanks @msabramo) and adds support for using VCR as a decorator (thanks @smallcode for the motivation)
* 0.5.0: Change the `response_of` method to `responses_of` since cassettes can now contain more than one response for a request.  Since this changes the API, I'm bumping the version.  Also includes 2 bugfixes: a better error message when attempting to overwrite a cassette file, and a fix for a bug with requests sessions (thanks @msabramo)
* 0.4.0: Change default request recording behavior for multiple requests.  If you make the same request multiple times to the same URL, the response might be different each time (maybe the response has a timestamp in it or something), so this will make the same request multiple times and save them all.  Then, when you are replaying the cassette, the responses will be played back in the same order in which they were received.  If you were making multiple requests to the same URL in a cassette before version 0.4.0, you might need to regenerate your cassette files.  Also, removes support for the cassette.play_count counter API, since individual requests aren't unique anymore.  A cassette might contain the same request several times.  Also removes secure overwrite feature since that was breaking overwriting files in Windows, and fixes a bug preventing request's automatic body decompression from working.
* 0.3.5: Fix compatibility with requests 2.x
* 0.3.4: Bugfix: close file before renaming it.  This fixes an issue on Windows.  Thanks @smallcode for the fix.
* 0.3.3: Bugfix for error message when an unreigstered custom matcher
  was used
* 0.3.2: Fix issue with new config syntax and the `match_on` parameter.
  Thanks, @chromy!
* 0.3.1: Fix issue causing full paths to be sent on the HTTP request
  line.
* 0.3.0: *Backwards incompatible release* - Added support for record
  modes, and changed the default recording behavior to the "once" record
  mode.  Please see the documentation on record modes for more.  Added
  support for custom request matching, and changed the default request
  matching behavior to match only on the URL and method. Also,
  improved the httplib mocking to add support for the `HTTPConnection.send()`
  method.  This means that requests won't actually be sent until the
  response is read, since I need to record the entire request in order
  to match up the appropriate response.  I don't think this should cause
  any issues unless you are sending requests without ever loading the
  response (which none of the standard httplib wrappers do, as far as I
  know.  Thanks to @fatuhoku for some of the ideas and the motivation 
  behind this release.
* 0.2.1: Fixed missing modules in setup.py
* 0.2.0: Added configuration API, which lets you configure some settings
  on VCR (see the README). Also, VCR no longer saves cassettes if they
  haven't changed at all and supports JSON as well as YAML 
  (thanks @sirpengi).  Added amazing new skeumorphic logo, thanks @hairarrow.
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
