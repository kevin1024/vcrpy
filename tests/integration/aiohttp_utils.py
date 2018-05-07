import asyncio

import aiohttp


@asyncio.coroutine
def aiohttp_request(loop, method, url, output='text', encoding='utf-8', **kwargs):
    session = aiohttp.ClientSession(loop=loop)
    response_ctx = session.request(method, url, **kwargs)  # NOQA: E999

    response = yield from response_ctx.__aenter__()  # NOQA: E999
    if output == 'text':
        content = yield from response.text()  # NOQA: E999
    elif output == 'json':
        content = yield from response.json(encoding=encoding)  # NOQA: E999
    elif output == 'raw':
        content = yield from response.read()  # NOQA: E999

    response_ctx._resp.close()
    yield from session.close()

    return response, content
