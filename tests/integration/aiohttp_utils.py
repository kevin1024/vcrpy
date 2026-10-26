# flake8: noqa
import asyncio

import aiohttp


async def _read_until_eof(read):
    # Callers pass a lambda that reads ``response.content`` afresh on every call.
    # Bounded: if each access restarted the body (#927), the loop would never reach
    # EOF, and as it never yields to the event loop, a timeout could not stop it.
    chunks = []
    for _ in range(10_000):
        chunk = await read()
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
    raise AssertionError("response.content never reached EOF")


async def aiohttp_request(loop, method, url, output="text", encoding="utf-8", content_type=None, **kwargs):
    async with aiohttp.ClientSession(loop=loop) as session:
        response_ctx = session.request(method, url, **kwargs)

        response = await response_ctx.__aenter__()
        if output == "text":
            content = await response.text()
        elif output == "json":
            content_type = content_type or "application/json"
            content = await response.json(encoding=encoding, content_type=content_type)
        elif output == "raw":
            content = await response.read()
        elif output == "stream":
            content = await response.content.read()
        elif output == "stream_chunked":
            content = b"".join([chunk async for chunk in response.content.iter_chunked(1024)])
        elif output == "stream_any":
            content = b"".join([chunk async for chunk in response.content.iter_any()])
        elif output == "stream_chunks":
            content = b"".join([chunk async for chunk, _ in response.content.iter_chunks()])
        elif output == "stream_lines":
            # Read ``response.content`` afresh for every line, as google-genai does (#927).
            content = await _read_until_eof(lambda: response.content.readline())
        elif output == "stream_until":
            # Like aiohttp, ``readuntil()`` returns what is left at EOF, then b"".
            content = await _read_until_eof(lambda: response.content.readuntil(b"\n\n"))

        response_ctx._resp.close()
        await session.close()

        return response, content


# A server-sent event on a single 600 KB line: longer than aiohttp's default line
# limit (twice ``read_bufsize``: 128 KiB before aiohttp 3.14, 512 KiB since).
LONG_LINE_BODY = b"data: " + b"x" * 600_000 + b"\n\n"


def aiohttp_app():
    async def hello(request):
        return aiohttp.web.Response(text="hello")

    async def json(request):
        return aiohttp.web.json_response({})

    async def json_empty_body(request):
        return aiohttp.web.json_response()

    async def long_line(request):
        return aiohttp.web.Response(body=LONG_LINE_BODY, content_type="text/event-stream")

    app = aiohttp.web.Application()
    app.router.add_get("/", hello)
    app.router.add_get("/json", json)
    app.router.add_get("/json/empty", json_empty_body)
    app.router.add_get("/long-line", long_line)
    return app
