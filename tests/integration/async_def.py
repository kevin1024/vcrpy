import aiohttp
import pytest
import vcr


@vcr.use_cassette()
@pytest.mark.asyncio
async def test_http():  # noqa: E999
    async with aiohttp.ClientSession() as session:
        url = 'https://httpbin.org/get'
        params = {'ham': 'spam'}
        resp = await session.get(url, params=params)  # noqa: E999
        assert (await resp.json())['args'] == {'ham': 'spam'}  # noqa: E999
