import logging
from .config import VCR

# Set default logging handler to avoid "No handler found" warnings.
import logging
try:  # Python 2.7+
    from logging import NullHandler
except ImportError:
    class NullHandler(logging.Handler):
        def emit(self, record):
            pass

logging.getLogger(__name__).addHandler(NullHandler())

default_vcr = VCR()


def use_cassette(path, **kwargs):
    return default_vcr.use_cassette(path, **kwargs)
