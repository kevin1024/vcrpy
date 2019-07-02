'''Stubs for aiohttp HTTP clients'''
from __future__ import absolute_import

import asyncio
import functools
import json

import multidict
from aiohttp import ClientResponse, streams
from vcr.request import Request
from yarl import URL


class MockStream(asyncio.StreamReader, streams.AsyncStreamReaderMixin):
    pass


class MockClientResponse(ClientResponse):
    def __init__(self, method, url):
        super().__init__(
            method=method,
            url=url,
            writer=None,
            continue100=None,
            timer=None,
            request_info=None,
            traces=None,
            loop=asyncio.get_event_loop(),
            session=None,
        )

    async def json(self, *, encoding='utf-8', loads=json.loads,
                   **kwargs):  # NOQA: E999
        stripped = self._body.strip()
        if not stripped:
            return None

        return loads(stripped.decode(encoding))

    async def text(self, encoding='utf-8', errors='strict'):
        return self._body.decode(encoding, errors=errors)

    async def read(self):
        return self._body

    def release(self):
        pass

    @property
    def content(self):
        s = MockStream()
        s.feed_data(self._body)
        s.feed_eof()
        return s


def vcr_request(cassette, real_request):
    @functools.wraps(real_request)
    async def new_request(self, method, url, **kwargs):
        headers = kwargs.get('headers')
        headers = self._prepare_headers(headers)
        data = kwargs.get('data')
        params = kwargs.get('params')

        request_url = URL(url)
        if params:
            new_params = multidict.MultiDict()
            for k, v in params.items():
                new_params.add(k, str(v))
            request_url = URL(url).with_query(new_params)

        vcr_request = Request(method, str(request_url), data, headers)

        if cassette.can_play_response_for(vcr_request):
            vcr_response = cassette.play_response(vcr_request)

            response = MockClientResponse(method, URL(vcr_response.get('url')))
            response.status = vcr_response['status']['code']
            response._body = vcr_response['body']['string']
            response.reason = vcr_response['status']['message']
            response._headers = vcr_response['headers']

            response.close()
            return response

        if cassette.write_protected and cassette.filter_request(vcr_request):
            response = MockClientResponse(method, URL(url))
            response.status = 599
            msg = ("No match for the request {!r} was found. Can't overwrite "
                   "existing cassette {!r} in your current record mode {!r}.")
            msg = msg.format(vcr_request, cassette._path, cassette.record_mode)
            response._body = msg.encode()
            response.close()
            return response

        response = await real_request(self, method, url,
                                      **kwargs)  # NOQA: E999

        vcr_response = {
            'status': {
                'code': response.status,
                'message': response.reason,
            },
            'headers': dict(response.headers),
            'body': {
                'string': (await response.read())
            },  # NOQA: E999
            'url': response.url,
        }
        cassette.append(vcr_request, vcr_response)

        return response

    return new_request
