from six.moves.urllib.request import urlopen

import vcr


def test_ignore_localhost(tmpdir, httpserver):
    httpserver.serve_content('Hello!')
    cass_file = str(tmpdir.join('filter_qs.yaml'))
    with vcr.use_cassette(cass_file, ignore_localhost=True) as cass:
        urlopen(httpserver.url)
        assert len(cass) == 0
        urlopen('http://httpbin.org')
        assert len(cass) == 1


def test_ignore_httpbin(tmpdir, httpserver):
    httpserver.serve_content('Hello!')
    cass_file = str(tmpdir.join('filter_qs.yaml'))
    with vcr.use_cassette(
        cass_file,
        ignore_hosts=['httpbin.org']
    ) as cass:
        urlopen('http://httpbin.org')
        assert len(cass) == 0
        urlopen(httpserver.url)
        assert len(cass) == 1


def test_ignore_localhost_and_httpbin(tmpdir, httpserver):
    httpserver.serve_content('Hello!')
    cass_file = str(tmpdir.join('filter_qs.yaml'))
    with vcr.use_cassette(
        cass_file,
        ignore_hosts=['httpbin.org'],
        ignore_localhost=True
    ) as cass:
        urlopen('http://httpbin.org')
        urlopen(httpserver.url)
        assert len(cass) == 0


def test_ignore_localhost_twice(tmpdir, httpserver):
    httpserver.serve_content('Hello!')
    cass_file = str(tmpdir.join('filter_qs.yaml'))
    with vcr.use_cassette(cass_file, ignore_localhost=True) as cass:
        urlopen(httpserver.url)
        assert len(cass) == 0
        urlopen('http://httpbin.org')
        assert len(cass) == 1
    with vcr.use_cassette(cass_file, ignore_localhost=True) as cass:
        assert len(cass) == 1
        urlopen(httpserver.url)
        urlopen('http://httpbin.org')
        assert len(cass) == 1
