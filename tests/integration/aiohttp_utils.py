# flake8: noqa
import asyncio

import aiohttp


@asyncio.coroutine
def aiohttp_request(loop, method, url, output='text', encoding='utf-8', content_type=None, **kwargs):
    session = aiohttp.ClientSession(loop=loop)
    response_ctx = session.request(method, url, **kwargs)

    response = yield from response_ctx.__aenter__()
    if output == 'text':
        content = yield from response.text()
    elif output == 'json':
        content_type = content_type or 'application/json'
        content = yield from response.json(encoding=encoding, content_type=content_type)
    elif output == 'raw':
        content = yield from response.read()

    response_ctx._resp.close()
    yield from session.close()

    return response, content
