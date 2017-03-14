import asyncio


@asyncio.coroutine
def handle_coroutine(vcr, fn):
    with vcr as cassette:
        return (yield from fn(cassette))  # noqa: E999
