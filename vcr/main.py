from __future__ import print_function
from __future__ import unicode_literals

import os
import sys
import argparse
import logging
import tempfile
import mimetypes
import cgi
import subprocess

from six.moves import shlex_quote

from .serializers import yamlserializer, jsonserializer


logger = logging.getLogger(__name__)


SUPPORTED_FORMATS = {
    '.yaml': (yamlserializer, ('.yaml', '.yml')),
    '.json': (jsonserializer, ('.json',)),
}


def guess_serializer(filename):
    for serializer, extensions in SUPPORTED_FORMATS.values():
        if filename.endswith(extensions):
            return serializer


def guess_extension(headers):
    if headers.get('Content-Type'):
        content_type = headers['Content-Type'][0]
        mime_type, _ = cgi.parse_header(content_type)
        return mimetypes.guess_extension(mime_type)
    else:
        return '.txt'


def edit_file_in_editor(path):
    cmd = '%s %s' % (os.environ.get('EDITOR', 'vi'), shlex_quote(path))
    subprocess.check_call(cmd, shell=True)


def edit_track(cassette_filename, serializer, data, track_no, field):
    track = data['interactions'][track_no]
    suffix = guess_extension(track[field]['headers'])

    with tempfile.NamedTemporaryFile('w', suffix=suffix, delete=False) as tf:
        if field == 'response':
            tf.write(track[field]['body']['string'])
        else:
            tf.write(track[field]['body'] or '')

    edit_file_in_editor(tf.name)

    with open(tf.name) as f:
        if field == 'response':
            track[field]['body']['string'] = f.read()
        else:
            track[field]['body'] = f.read() or None

    cassette_content = serializer.serialize(data)
    with open(cassette_filename, 'w') as f:
        f.write(cassette_content)
    logger.info("cassette has been updated successfully")

    os.unlink(tf.name)


def list_tracks(stdout, data):
    for i, interaction in enumerate(data['interactions']):
        request = interaction['request']
        print('%3d %5s %s' % (i, request['method'], request['uri']),
              file=stdout)


def main(argv=None, stdout=sys.stdout):
    parser = argparse.ArgumentParser()
    parser.add_argument('cassette', help="vcrpy cassette file")
    parser.add_argument('track', nargs='?', type=int,
                        help="vcrpy cassette track to work with")
    parser.add_argument('-e', '--edit', choices=['request', 'response'],
                        help="open editor with specified data to edit")
    args = parser.parse_args(argv)

    logging.basicConfig(format='%(message)s', level=logging.INFO)

    serializer = guess_serializer(args.cassette)

    if serializer is None:
        logger.error((
            "Unknown cassette file format, supported formats are: %s"
        ) % ', '.join(sorted(SUPPORTED_FORMATS.keys())))
        return 1

    with open(args.cassette) as f:
        cassette_content = f.read()

    data = serializer.deserialize(cassette_content)

    if args.track is not None and args.edit:
        edit_track(args.cassette, serializer, data, args.track, args.edit)
    else:
        list_tracks(stdout, data)


if __name__ == "__main__":
    sys.exit(main() or 0)  # pragma: no cover
