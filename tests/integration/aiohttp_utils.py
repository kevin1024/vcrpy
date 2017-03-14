import asyncio
import aiohttp


@asyncio.coroutine
def aiohttp_request(loop, method, url, as_text, **kwargs):
    with aiohttp.ClientSession(loop=loop) as session:
        response = yield from session.request(method, url, **kwargs)  # NOQA: E999
        if as_text:
            content = yield from response.text()  # NOQA: E999
        else:
            content = yield from response.json()  # NOQA: E999
        return response, content
