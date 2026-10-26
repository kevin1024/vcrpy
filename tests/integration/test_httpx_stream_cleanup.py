import asyncio

import pytest

import vcr


@pytest.fixture(params=["httpx", "httpx2"])
def httpx_module(request):
    return pytest.importorskip(request.param)


@pytest.mark.parametrize("close_fails", [False, True])
def test_recording_closes_failed_sync_stream(tmp_path, httpx_module, close_fails):
    httpx = httpx_module
    read_error = httpx.ReadError("reading failed")
    closed = []

    class Stream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"partial"
            raise read_error

        def close(self):
            closed.append(True)
            if close_fails:
                raise RuntimeError("closing failed")

    transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=Stream()))
    with (
        httpx.Client(transport=transport) as client,
        vcr.use_cassette(str(tmp_path / "failed.yaml")) as cassette,
    ):
        with (
            pytest.raises(httpx.ReadError) as caught,
            client.stream("GET", "http://example.invalid/") as response,
        ):
            response.read()
        assert caught.value is read_error
        assert closed == [True]
        assert len(cassette) == 0


def test_recording_closes_failed_wsgi_iterable(tmp_path, httpx_module):
    httpx = httpx_module
    closed = []

    class Body:
        def __iter__(self):
            yield b"partial"
            raise RuntimeError("application iterator failed")

        def close(self):
            closed.append(True)

    def app(environ, start_response):
        start_response("200 OK", [("Content-Type", "text/plain")])
        return Body()

    with (
        httpx.Client(transport=httpx.WSGITransport(app=app)) as client,
        vcr.use_cassette(str(tmp_path / "wsgi.yaml")) as cassette,
    ):
        with (
            pytest.raises(RuntimeError, match="application iterator failed"),
            client.stream("GET", "http://example.invalid/") as response,
        ):
            response.read()
        assert closed == [True]
        assert len(cassette) == 0


@pytest.mark.parametrize("close_fails", [False, True])
def test_recording_closes_failed_async_stream(tmp_path, httpx_module, close_fails):
    httpx = httpx_module
    read_error = httpx.ReadError("reading failed")
    closed = []

    class Stream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"partial"
            raise read_error

        async def aclose(self):
            await asyncio.sleep(0)
            closed.append(True)
            if close_fails:
                raise RuntimeError("closing failed")

    async def run():
        transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=Stream()))
        async with httpx.AsyncClient(transport=transport) as client:
            with vcr.use_cassette(str(tmp_path / "failed.yaml")) as cassette:
                with pytest.raises(httpx.ReadError) as caught:
                    async with client.stream("GET", "http://example.invalid/") as response:
                        await response.aread()
                assert caught.value is read_error
                assert closed == [True]
                assert len(cassette) == 0

    asyncio.run(run())


@pytest.mark.parametrize("close_fails", [False, True])
def test_recording_closes_cancelled_async_stream(tmp_path, httpx_module, close_fails):
    httpx = httpx_module

    async def run():
        reading = asyncio.Event()
        closed = []

        class Stream(httpx.AsyncByteStream):
            async def __aiter__(self):
                yield b"partial"
                reading.set()
                await asyncio.Event().wait()

            async def aclose(self):
                await asyncio.sleep(0)
                closed.append(True)
                if close_fails:
                    raise RuntimeError("closing failed")

        transport = httpx.MockTransport(lambda request: httpx.Response(200, stream=Stream()))
        async with httpx.AsyncClient(transport=transport) as client:
            with vcr.use_cassette(str(tmp_path / "cancelled.yaml")) as cassette:

                async def request():
                    try:
                        await client.get("http://example.invalid/")
                    except asyncio.CancelledError as exc:
                        # Python 3.10 does not propagate the message across Task boundaries.
                        assert str(exc) == "caller cancelled"
                        raise

                task = asyncio.create_task(request())
                try:
                    await asyncio.wait_for(reading.wait(), 2)
                finally:
                    task.cancel("caller cancelled")
                    with pytest.raises(asyncio.CancelledError):
                        await task
                assert closed == [True]
                assert len(cassette) == 0

    asyncio.run(run())


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("close_fails", [False, True])
def test_recording_closes_completed_stream_once(tmp_path, httpx_module, asynchronous, close_fails):
    httpx = httpx_module
    closed = []
    close_error = RuntimeError("closing failed")

    def close():
        closed.append(True)
        if close_fails:
            raise close_error

    class SyncStream(httpx.SyncByteStream):
        def __iter__(self):
            yield b"complete"

        def close(self):
            close()

    class AsyncStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"complete"

        async def aclose(self):
            await asyncio.sleep(0)
            close()

    def request():
        with httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=SyncStream())),
        ) as client:
            return client.get("http://example.invalid/")

    async def async_request():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=AsyncStream())),
        ) as client:
            return await client.get("http://example.invalid/")

    def perform_request():
        return asyncio.run(async_request()) if asynchronous else request()

    path = str(tmp_path / "completed.yaml")
    with vcr.use_cassette(path) as cassette:
        if close_fails:
            with pytest.raises(RuntimeError) as caught:
                perform_request()
            assert caught.value is close_error
            assert len(cassette) == 0
        else:
            assert perform_request().content == b"complete"
            assert len(cassette) == 1
        assert closed == [True]

    if not close_fails:
        with vcr.use_cassette(path) as cassette:
            assert perform_request().content == b"complete"
            assert cassette.play_count == 1
        assert closed == [True]
