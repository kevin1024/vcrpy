import logging
import warnings
import sys
from .config import VCR
from logging import NullHandler

if sys.version_info[0] == 2:
    warnings.warn(
        "Python 2.x support of vcrpy is deprecated and will be removed in an upcoming major release.",
        DeprecationWarning
    )

logging.getLogger(__name__).addHandler(NullHandler())


default_vcr = VCR()
use_cassette = default_vcr.use_cassette
