import aiohttp


async def aiohttp_request(loop, method, url, output='text', **kwargs):  # NOQA: E999
    async with aiohttp.ClientSession(loop=loop) as session:  # NOQA: E999
        async with session.request(method, url, **kwargs) as response:  # NOQA: E999
            if output == 'text':
                content = await response.text()  # NOQA: E999
            elif output == 'json':
                content = await response.json()  # NOQA: E999
            elif output == 'raw':
                content = await response.read()  # NOQA: E999
            return response, content
