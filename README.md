#VCR.py

This is a proof-of-concept start at a python version of [Ruby's VCR
library](https://github.com/myronmarston/vcr).  It
doesn't actually work.

#What it is supposed to do
Simplify testing by recording all HTTP interactions and saving them to
"cassette" files, which are just yaml files.  Then when you run your tests
again, they all just hit the text files instead of the internet.  This speeds up
your tests and lets you work offline.

#What it actually does
Uses up all your memory


#Similar libraries in Python
Neither of these really implement the API I want, but I have cribbed some code
from them.
 * https://github.com/bbangert/Dalton
 * https://github.com/storborg/replaylib
