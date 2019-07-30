'''Stubs for aiohttp HTTP clients'''
from __future__ import absolute_import

import asyncio
import functools
import logging
import json

from aiohttp import ClientResponse, streams
from multidict import CIMultiDict, CIMultiDictProxy
from yarl import URL

from vcr.request import Request

log = logging.getLogger(__name__)


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

    async def json(self, *, encoding='utf-8', loads=json.loads, **kwargs):  # NOQA: E999
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


def build_response(vcr_request, vcr_response, history):
    response = MockClientResponse(vcr_request.method, URL(vcr_response.get('url')))
    response.status = vcr_response['status']['code']
    response._body = vcr_response['body'].get('string', b'')
    response.reason = vcr_response['status']['message']
    response._headers = CIMultiDictProxy(CIMultiDict(vcr_response['headers']))
    response._history = tuple(history)

    response.close()
    return response


def play_responses(cassette, vcr_request):
    history = []
    vcr_response = cassette.play_response(vcr_request)
    response = build_response(vcr_request, vcr_response, history)

    while cassette.can_play_response_for(vcr_request):
        history.append(response)
        vcr_response = cassette.play_response(vcr_request)
        response = build_response(vcr_request, vcr_response, history)

    return response


async def record_response(cassette, vcr_request, response, past=False):
    body = {} if past else {'string': (await response.read())}
    headers = {str(key): value for key, value in response.headers.items()}

    vcr_response = {
        'status': {
            'code': response.status,
            'message': response.reason,
        },
        'headers': headers,
        'body': body,  # NOQA: E999
        'url': str(response.url),
    }
    cassette.append(vcr_request, vcr_response)


async def record_responses(cassette, vcr_request, response):
    for past_response in response.history:
        await record_response(cassette, vcr_request, past_response, past=True)

    await record_response(cassette, vcr_request, response)


def vcr_request(cassette, real_request):
    @functools.wraps(real_request)
    async def new_request(self, method, url, **kwargs):
        headers = kwargs.get('headers')
        auth = kwargs.get('auth')
        headers = self._prepare_headers(headers)
        data = kwargs.get('data', kwargs.get('json'))
        params = kwargs.get('params')

        if auth is not None:
            headers['AUTHORIZATION'] = auth.encode()

        request_url = URL(url)
        if params:
            for k, v in params.items():
                params[k] = str(v)
            request_url = URL(url).with_query(params)

        vcr_request = Request(method, str(request_url), data, headers)

        if cassette.can_play_response_for(vcr_request):
            return play_responses(cassette, vcr_request)

        if cassette.write_protected and cassette.filter_request(vcr_request):
            response = MockClientResponse(method, URL(url))
            response.status = 599
            msg = ("No match for the request {!r} was found. Can't overwrite "
                   "existing cassette {!r} in your current record mode {!r}.")
            msg = msg.format(vcr_request, cassette._path, cassette.record_mode)
            response._body = msg.encode()
            response.close()
            return response

        log.info('%s not in cassette, sending to real server', vcr_request)

        response = await real_request(self, method, url, **kwargs)  # NOQA: E999
        await record_responses(cassette, vcr_request, response)
        return response

    return new_request
