from six import StringIO
from six.moves.urllib.request import urlopen

import vcr

from vcr.main import main, edit_file_in_editor
from vcr.compat import mock
from vcr.serializers import yamlserializer


def test_list_tracks(tmpdir, httpbin):
    cassette_filename = tmpdir.join('test.yml')
    with vcr.use_cassette(str(cassette_filename)):
        urlopen(httpbin.url + '/xml')
        urlopen(httpbin.url + '/xml')

    stdout = StringIO()
    assert main([str(cassette_filename)], stdout) is None

    assert stdout.getvalue().splitlines() == [
        '  0   GET %s/xml' % httpbin.url,
        '  1   GET %s/xml' % httpbin.url,
    ]


def test_edit_track_response(tmpdir, httpbin, mocker):
    mocker.patch('vcr.main.edit_file_in_editor', side_effect=write('new'))

    cassette_filename = tmpdir.join('test.yml')
    with vcr.use_cassette(str(cassette_filename)):
        urlopen(httpbin.url + '/xml')
        urlopen(httpbin.url + '/xml')

    stdout = StringIO()
    assert main([str(cassette_filename), '0', '-e', 'response'], stdout) is None

    assert stdout.getvalue().splitlines() == []

    cassette = yamlserializer.deserialize(cassette_filename.read())
    assert cassette['interactions'][0]['response']['body']['string'] == 'new'


def test_edit_track_request(tmpdir, httpbin, mocker):
    mocker.patch('vcr.main.edit_file_in_editor', side_effect=write('new'))

    cassette_filename = tmpdir.join('test.yml')
    with vcr.use_cassette(str(cassette_filename)):
        urlopen(httpbin.url + '/xml')
        urlopen(httpbin.url + '/xml')

    stdout = StringIO()
    assert main([str(cassette_filename), '1', '-e', 'request'], stdout) is None

    assert stdout.getvalue().splitlines() == []

    cassette = yamlserializer.deserialize(cassette_filename.read())
    assert cassette['interactions'][1]['request']['body'] == 'new'


def test_edit_file_in_editor(mocker):
    mocker.patch.dict('os.environ', {'EDITOR': 'vi'})
    check_call = mocker.patch('subprocess.check_call')
    edit_file_in_editor('/tmp/foo/bar')
    assert check_call.mock_calls == [
        mock.call('vi /tmp/foo/bar', shell=True),
    ]


def test_unknown_format():
    stdout = StringIO()
    assert main(['/dev/null'], stdout) == 1
    assert stdout.getvalue().splitlines() == []


def write(content):
    def func(path):
        with open(path, 'w') as f:
            f.write(content)
    return func
