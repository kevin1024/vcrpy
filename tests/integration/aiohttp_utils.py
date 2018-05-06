import asyncio
import aiohttp


@asyncio.coroutine
def aiohttp_request(loop, method, url, output='text', **kwargs):
    with aiohttp.ClientSession(loop=loop) as session:
        response = yield from session.request(method, url, **kwargs)  # NOQA: E999
        if output == 'text':
            content = yield from response.text()  # NOQA: E999
        elif output == 'json':
            content = yield from response.json()  # NOQA: E999
        elif output == 'raw':
            content = yield from response.read()  # NOQA: E999
        return response, content
