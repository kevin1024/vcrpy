'''Stubs for aiohttp HTTP clients'''
from __future__ import absolute_import

import asyncio
import functools
import json
import urllib

from aiohttp import ClientResponse, helpers

from vcr.request import Request


class MockClientResponse(ClientResponse):
    # TODO: get encoding from header
    @asyncio.coroutine
    def json(self, *, encoding='utf-8', loads=json.loads):  # NOQA: E999
        return loads(self.content.decode(encoding))

    @asyncio.coroutine
    def text(self, encoding='utf-8'):
        return self.content.decode(encoding)

    @asyncio.coroutine
    def release(self):
        pass


def vcr_request(cassette, real_request):
    @functools.wraps(real_request)
    @asyncio.coroutine
    def new_request(self, method, url, **kwargs):
        headers = kwargs.get('headers')
        headers = self._prepare_headers(headers)
        data = kwargs.get('data')
        params = kwargs.get('params')

        # INFO: Query join logic from
        # https://github.com/KeepSafe/aiohttp/blob/b3eeedbc2f515ec2aa6e87ba129524c17b6fe4e3/aiohttp/client_reqrep.py#L167-L188
        scheme, netloc, path, query, fragment = urllib.parse.urlsplit(url)
        if not path:
            path = '/'

        # NOTICE: Not sure this is applicable here:
        # if isinstance(params, collections.Mapping):
        #     params = list(params.items())

        if params:
            if not isinstance(params, str):
                params = urllib.parse.urlencode(params)
            if query:
                query = '%s&%s' % (query, params)
            else:
                query = params

        request_path = urllib.parse.urlunsplit(('', '', helpers.requote_uri(path),
                                                query, fragment))
        request_url = urllib.parse.urlunsplit(
            (scheme, netloc, request_path, '', ''))

        vcr_request = Request(method, request_url, data, headers)

        if cassette.can_play_response_for(vcr_request):
            vcr_response = cassette.play_response(vcr_request)

            response = MockClientResponse(method, vcr_response.get('url'))
            response.status = vcr_response['status']['code']
            response.content = vcr_response['body']['string']
            response.reason = vcr_response['status']['message']
            response.headers = vcr_response['headers']

            response.close()
            return response

        if cassette.write_protected and cassette.filter_request(vcr_request):
            response = MockClientResponse(method, url)
            response.status = 599
            msg = ("No match for the request {!r} was found. Can't overwrite "
                   "existing cassette {!r} in your current record mode {!r}.")
            msg = msg.format(vcr_request, cassette._path, cassette.record_mode)
            response.content = msg.encode()
            response.close()
            return response

        response = yield from real_request(self, method, url, **kwargs)  # NOQA: E999

        vcr_response = {
            'status': {
                'code': response.status,
                'message': response.reason,
            },
            'headers': dict(response.headers),
            'body': {'string': (yield from response.text())},  # NOQA: E999
            'url': response.url,
        }
        cassette.append(vcr_request, vcr_response)

        return response

    return new_request
