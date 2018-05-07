# flake8: noqa
import aiohttp


async def aiohttp_request(loop, method, url, output='text',
                          encoding='utf-8', headers=None, **kwargs):
    async with aiohttp.ClientSession(loop=loop, headers=headers or {}) as session:
        async with session.request(method, url, **kwargs) as response:
            if output == 'text':
                content = await response.text()
            elif output == 'json':
                content = await response.json(encoding=encoding)
            elif output == 'raw':
                content = await response.read()

            return response, content
