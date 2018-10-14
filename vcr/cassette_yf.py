def _loc_handle_generator(self, fn):
    """Wraps a generator so that we're inside the cassette context for the
    duration of the generator.
    """
    with self as cassette:
        coroutine = fn(cassette)
        yield from coroutine
