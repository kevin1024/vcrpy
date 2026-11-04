from __future__ import annotations

import inspect
import os
import sys
import unittest
from typing import TYPE_CHECKING, Unpack

from .config import VCR

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

if TYPE_CHECKING:
    from .cassette import Cassette
    from .types import VCROptions

    # The mixin is for TestCases; type checkers see it as one, so its methods can use TestCase's.
    _MixinBase = unittest.TestCase
else:
    _MixinBase = object


class VCRMixin(_MixinBase):
    """A TestCase mixin that provides VCR integration."""

    vcr_enabled = True
    cassette: Cassette

    @override
    def setUp(self) -> None:
        super().setUp()
        if self.vcr_enabled:
            kwargs = self._get_vcr_kwargs()
            myvcr = self._get_vcr(**kwargs)
            cm = myvcr.use_cassette(self._get_cassette_name())
            self.cassette = cm.__enter__()
            self.addCleanup(cm.__exit__, None, None, None)

    def _get_vcr(self, **kwargs: Unpack[VCROptions]) -> VCR:
        if "cassette_library_dir" not in kwargs:
            kwargs["cassette_library_dir"] = self._get_cassette_library_dir()
        return VCR(**kwargs)

    def _get_vcr_kwargs(self, **kwargs: Unpack[VCROptions]) -> VCROptions:
        return kwargs

    def _get_cassette_library_dir(self) -> str:
        testdir = os.path.dirname(inspect.getfile(self.__class__))
        return os.path.join(testdir, "cassettes")

    def _get_cassette_name(self) -> str:
        return f"{self.__class__.__name__}.{self._testMethodName}.yaml"


class VCRTestCase(VCRMixin, unittest.TestCase):
    pass
