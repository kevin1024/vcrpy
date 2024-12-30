import logging
from logging import NullHandler

from .config import VCR
from .record_mode import RecordMode as mode  # noqa: F401

__version__ = "7.0.0"

logging.getLogger(__name__).addHandler(NullHandler())


default_vcr = VCR()
use_cassette = default_vcr.use_cassette
