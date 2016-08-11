import asyncio


@asyncio.coroutine
def aiohttp_request(session, method, url, as_text, **kwargs):
    response = yield from session.request(method, url, **kwargs)  # NOQA: E999
    return response, (yield from response.text()) if as_text else (yield from response.json())  # NOQA: E999
