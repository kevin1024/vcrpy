from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import AbstractContextManager
from typing import TypeVar

_T = TypeVar("_T")
_R = TypeVar("_R")


async def handle_coroutine(vcr: AbstractContextManager[_T], fn: Callable[[_T], Awaitable[_R]]) -> _R:
    with vcr as cassette:
        return await fn(cassette)
