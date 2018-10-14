# -*- coding: utf-8 -*-

import sys

def _loc_handle_generator(self, fn):
    """Wraps a generator so that we're inside the cassette context for the
    duration of the generator.
    """
    with self as cassette:
        coroutine = fn(cassette)

        to_yield = next(coroutine)
        while True:
            try:
                to_send = yield to_yield
            except Exception:
                to_yield = coroutine.throw(*sys.exc_info())
            else:
                try:
                   to_yield = coroutine.send(to_send)
                except StopIteration:
                    break
