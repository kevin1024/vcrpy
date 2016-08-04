'''Stubs for aiohttp HTTP clients'''
from __future__ import absolute_import

import functools
import json

from aiohttp import ClientResponse

from vcr.request import Request


class MockClientResponse(ClientResponse):
    # TODO: get encoding from header
    async def json(self, *, encoding='utf-8', loads=json.loads):
        return loads(self.content.decode(encoding))

    async def text(self, encoding='utf-8'):
        return self.content.decode(encoding)

    async def release(self):
        self.close()


def vcr_request(cassette, real_request):

    @functools.wraps(real_request)
    async def new_request(self, method, url, **kwargs):
        headers = kwargs.get('headers')
        headers = self._prepare_headers(headers)
        data = kwargs.get('data')

        vcr_request = Request(method, url, data, headers)

        if cassette.can_play_response_for(vcr_request):
            vcr_response = cassette.play_response(vcr_request)

            response = MockClientResponse(method, vcr_response.get('url'))
            response.status = vcr_response['status']['code']
            response.content = vcr_response['body']['string']
            response.reason = vcr_response['status']['message']
            response.headers = vcr_response['headers']

            return response

        if cassette.write_protected and cassette.filter_request(vcr_request):
            response = MockClientResponse(method, url)
            response.status = 599
            response.content = ("No match for the request (%r) was found. "
                                "Can't overwrite existing cassette (%r) in "
                                "your current record mode (%r).")
            response.close()
            return response

        response = await real_request(self, method, url, **kwargs)

        vcr_response = {
            'status': {
                'code': response.status,
                'message': response.reason,
            },
            'headers': response.headers,
            'body': {'string': await response.text()},
            'url': response.url,
        }
        cassette.append(vcr_request, vcr_response)

        return response

    return new_request
