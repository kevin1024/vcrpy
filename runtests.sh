#!/bin/bash

# https://blog.ionelmc.ro/2015/04/14/tox-tricks-and-patterns/#when-it-inevitably-leads-to-shell-scripts
# If you are getting an INVOCATION ERROR for this script then there is 
# a good chance you are running on Windows.
# You can and should use WSL for running tox on Windows when it calls bash scripts.
REQUESTS_CA_BUNDLE=`python -m pytest_httpbin.certs` pytest $*
