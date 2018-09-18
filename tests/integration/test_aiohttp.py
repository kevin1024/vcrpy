import contextlib

import pytest
asyncio = pytest.importorskip("asyncio")
aiohttp = pytest.importorskip("aiohttp")

import vcr  # noqa: E402
from .aiohttp_utils import aiohttp_app, aiohttp_request  # noqa: E402


def run_in_loop(fn):
    with contextlib.closing(asyncio.new_event_loop()) as loop:
        asyncio.set_event_loop(loop)
        task = loop.create_task(fn(loop))
        return loop.run_until_complete(task)


def request(method, url, output='text', **kwargs):
    def run(loop):
        return aiohttp_request(loop, method, url, output=output, **kwargs)

    return run_in_loop(run)


def get(url, output='text', **kwargs):
    return request('GET', url, output=output, **kwargs)


def post(url, output='text', **kwargs):
    return request('POST', url, output='text', **kwargs)


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
    headers = {'Content-Type': 'application/json'}

    with vcr.use_cassette(str(tmpdir.join('json.yaml'))):
        _, response_json = get(url, output='json', headers=headers)

    with vcr.use_cassette(str(tmpdir.join('json.yaml'))) as cassette:
        _, cassette_response_json = get(url, output='json', headers=headers)
        assert cassette_response_json == response_json
        assert cassette.play_count == 1


def test_binary(tmpdir, scheme):
    url = scheme + '://httpbin.org/image/png'
    with vcr.use_cassette(str(tmpdir.join('binary.yaml'))):
        _, response_binary = get(url, output='raw')

    with vcr.use_cassette(str(tmpdir.join('binary.yaml'))) as cassette:
        _, cassette_response_binary = get(url, output='raw')
        assert cassette_response_binary == response_binary
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
    headers = {'Content-Type': 'application/json'}
    params = {'a': 1, 'b': False, 'c': 'c'}

    with vcr.use_cassette(str(tmpdir.join('get.yaml'))) as cassette:
        _, response_json = get(url, output='json', params=params, headers=headers)

    with vcr.use_cassette(str(tmpdir.join('get.yaml'))) as cassette:
        _, cassette_response_json = get(url, output='json', params=params, headers=headers)
        assert cassette_response_json == response_json
        assert cassette.play_count == 1


def test_params_same_url_distinct_params(tmpdir, scheme):
    url = scheme + '://httpbin.org/get'
    headers = {'Content-Type': 'application/json'}
    params = {'a': 1, 'b': False, 'c': 'c'}

    with vcr.use_cassette(str(tmpdir.join('get.yaml'))) as cassette:
        _, response_json = get(url, output='json', params=params, headers=headers)

    with vcr.use_cassette(str(tmpdir.join('get.yaml'))) as cassette:
        _, cassette_response_json = get(url, output='json', params=params, headers=headers)
        assert cassette_response_json == response_json
        assert cassette.play_count == 1

    other_params = {'other': 'params'}
    with vcr.use_cassette(str(tmpdir.join('get.yaml'))) as cassette:
        response, cassette_response_text = get(url, output='text', params=other_params)
        assert 'No match for the request' in cassette_response_text
        assert response.status == 599


def test_params_on_url(tmpdir, scheme):
    url = scheme + '://httpbin.org/get?a=1&b=foo'
    headers = {'Content-Type': 'application/json'}

    with vcr.use_cassette(str(tmpdir.join('get.yaml'))) as cassette:
        _, response_json = get(url, output='json', headers=headers)
        request = cassette.requests[0]
        assert request.url == url

    with vcr.use_cassette(str(tmpdir.join('get.yaml'))) as cassette:
        _, cassette_response_json = get(url, output='json', headers=headers)
        request = cassette.requests[0]
        assert request.url == url
        assert cassette_response_json == response_json
        assert cassette.play_count == 1


def test_aiohttp_test_client(aiohttp_client, tmpdir):
    loop = asyncio.get_event_loop()
    app = aiohttp_app()
    url = '/'
    client = loop.run_until_complete(aiohttp_client(app))

    with vcr.use_cassette(str(tmpdir.join('get.yaml'))):
        response = loop.run_until_complete(client.get(url))

    assert response.status == 200
    response_text = loop.run_until_complete(response.text())
    assert response_text == 'hello'

    with vcr.use_cassette(str(tmpdir.join('get.yaml'))) as cassette:
        response = loop.run_until_complete(client.get(url))

    request = cassette.requests[0]
    assert request.url == str(client.make_url(url))
    response_text = loop.run_until_complete(response.text())
    assert response_text == 'hello'
    assert cassette.play_count == 1
