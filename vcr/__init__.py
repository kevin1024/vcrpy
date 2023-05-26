import logging
from logging import NullHandler

from .config import VCR
from .record_mode import RecordMode as mode  # noqa import is not used in this file

__version__ = "4.3.1"

logging.getLogger(__name__).addHandler(NullHandler())


default_vcr = VCR()
use_cassette = default_vcr.use_cassette
