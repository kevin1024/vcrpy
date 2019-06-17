import logging
import warnings
import sys
from .config import VCR
from logging import NullHandler


logging.getLogger(__name__).addHandler(NullHandler())


default_vcr = VCR()
use_cassette = default_vcr.use_cassette
