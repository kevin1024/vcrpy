import logging
from .config import VCR
from . import cassette

# Set default logging handler to avoid "No handler found" warnings.
try:  # Python 2.7+
    from logging import NullHandler
except ImportError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass

def global_toggle(enabled=True):
    cassette.use_cassette._enabled = enabled


logging.getLogger(__name__).addHandler(NullHandler())


default_vcr = VCR()
use_cassette = default_vcr.use_cassette
