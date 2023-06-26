async def handle_coroutine(vcr, fn):
    with vcr as cassette:
        return await fn(cassette)
