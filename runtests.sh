#!/bin/bash

# If you are getting an INVOCATION ERROR for this script then there is a good chance you are running on Windows.
# You can and should use WSL for running tests on Windows when it calls bash scripts.
REQUESTS_CA_BUNDLE=`python3 -m pytest_httpbin.certs` exec pytest "$@"
