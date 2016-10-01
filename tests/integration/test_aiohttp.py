import pytest
aiohttp = pytest.importorskip("aiohttp")

import asyncio  # NOQA
import sys  # NOQA

import aiohttp  # NOQA
import pytest  # NOQA
import vcr  # NOQA

from .aiohttp_utils import aiohttp_request  # NOQA


def get(url, as_text=True, **kwargs):
    loop = asyncio.get_event_loop()
    with aiohttp.ClientSession() as session:
        task = loop.create_task(aiohttp_request(session, 'GET', url, as_text, **kwargs))
        return loop.run_until_complete(task)


def post(url, as_text=True, **kwargs):
    loop = asyncio.get_event_loop()
    with aiohttp.ClientSession() as session:
        task = loop.create_task(aiohttp_request(session, 'POST', url, as_text, **kwargs))
        return loop.run_until_complete(task)


@pytest.fixture(params=["https", "http"])
def scheme(request):
    '''Fixture that returns both http and https.'''
    return request.param


def test_status(tmpdir, scheme):
    url = scheme + '://httpbin.org'
    with vcr.use_cassette(str(tmpdir.join('status.yaml'))):
        response, _ = get(url)

    with vcr.use_cassette(str(tmpdir.join('status.yaml'))) as cassette:
        cassette_response, _ = get(url)
        assert cassette_response.status == response.status
        assert cassette.play_count == 1


def test_headers(tmpdir, scheme):
    url = scheme + '://httpbin.org'
    with vcr.use_cassette(str(tmpdir.join('headers.yaml'))):
        response, _ = get(url)

    with vcr.use_cassette(str(tmpdir.join('headers.yaml'))) as cassette:
        cassette_response, _ = get(url)
        assert cassette_response.headers == response.headers
        assert cassette.play_count == 1


def test_text(tmpdir, scheme):
    url = scheme + '://httpbin.org'
    with vcr.use_cassette(str(tmpdir.join('text.yaml'))):
        _, response_text = get(url)

    with vcr.use_cassette(str(tmpdir.join('text.yaml'))) as cassette:
        _, cassette_response_text = get(url)
        assert cassette_response_text == response_text
        assert cassette.play_count == 1


def test_json(tmpdir, scheme):
    url = scheme + '://httpbin.org/get'
    with vcr.use_cassette(str(tmpdir.join('json.yaml'))):
        _, response_json = get(url, as_text=False)

    with vcr.use_cassette(str(tmpdir.join('json.yaml'))) as cassette:
        _, cassette_response_json = get(url, as_text=False)
        assert cassette_response_json == response_json
        assert cassette.play_count == 1


def test_post(tmpdir, scheme):
    data = {'key1': 'value1', 'key2': 'value2'}
    url = scheme + '://httpbin.org/post'
    with vcr.use_cassette(str(tmpdir.join('post.yaml'))):
        _, response_json = post(url, data=data)

    with vcr.use_cassette(str(tmpdir.join('post.yaml'))) as cassette:
        _, cassette_response_json = post(url, data=data)
        assert cassette_response_json == response_json
        assert cassette.play_count == 1


def test_params(tmpdir, scheme):
    url = scheme + '://httpbin.org/get'
    params = {'a': 1, 'b': False, 'c': 'c'}
    with vcr.use_cassette(str(tmpdir.join('get.yaml'))) as cassette:
        _, response_json = get(url, as_text=False, params=params)

    with vcr.use_cassette(str(tmpdir.join('get.yaml'))) as cassette:
        _, cassette_response_json = get(url, as_text=False, params=params)
        assert cassette_response_json == response_json
        assert cassette.play_count == 1


def test_params_same_url_distinct_params(tmpdir, scheme):
    url = scheme + '://httpbin.org/get'
    params = {'a': 1, 'b': False, 'c': 'c'}
    with vcr.use_cassette(str(tmpdir.join('get.yaml'))) as cassette:
        _, response_json = get(url, as_text=False, params=params)

    with vcr.use_cassette(str(tmpdir.join('get.yaml'))) as cassette:
        _, cassette_response_json = get(url, as_text=False, params=params)
        assert cassette_response_json == response_json
        assert cassette.play_count == 1

    other_params = {'other': 'params'}
    with vcr.use_cassette(str(tmpdir.join('get.yaml'))) as cassette:
        response, cassette_response_text = get(url, as_text=True, params=other_params)
        assert 'No match for the request' in cassette_response_text
        assert response.status == 599
