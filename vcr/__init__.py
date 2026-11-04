from __future__ import annotations

import logging
from logging import NullHandler
from typing import Final

from .config import VCR
from .record_mode import RecordMode as mode
from .request import Request

__all__ = ["VCR", "Request", "__version__", "default_vcr", "mode", "use_cassette"]

__version__ = "9.4.2"

logging.getLogger(__name__).addHandler(NullHandler())


default_vcr: VCR = VCR()
use_cassette: Final = default_vcr.use_cassette
