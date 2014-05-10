"""
Migration script for old 'yaml' and 'json' cassettes

.. warning:: Backup your cassettes files before migration.

It merges and deletes the request obsolete keys (protocol, host, port, path)
into new 'uri' key.
Usage::

    python -m vcr.migration PATH

The PATH can be path to the directory with cassettes or cassette itself
"""

import json
import os
import shutil
import sys
import tempfile
import yaml

from .serializers import compat, yamlserializer, jsonserializer
from .serialize import serialize
from . import request
from .stubs.compat import get_httpmessage

# Use the libYAML versions if possible
try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

def preprocess_yaml(cassette):
    return cassette.replace(' !!python/object:vcr.request.Request', '').replace('!!python/object/apply:__builtin__.frozenset', '')


PARTS = [
    'protocol',
    'host',
    'port',
    'path',
]


def build_uri(**parts):
    port = parts['port']
    scheme = parts['protocol']
    default_port = {'https': 433, 'http': 80}[scheme]
    parts['port'] = ':{0}'.format(port) if port != default_port else ''
    return "{protocol}://{host}{port}{path}".format(**parts)


def _migrate(data):
    interactions = []
    for item in data:
        req = item['request']
        res = item['response']
        uri = dict((k, req.pop(k)) for k in PARTS)
        req['uri'] = build_uri(**uri)
        # convert headers to dict of lists
        headers = req['headers']
        for k in headers:
            headers[k] = [headers[k]]
        response_headers = {}
        for k, v in get_httpmessage(b"".join(h.encode('utf-8') for h in res['headers'])).items():
            response_headers.setdefault(k, [])
            response_headers[k].append(v)
        res['headers'] = response_headers
        interactions.append({'request':req, 'response': res})
    return {
        'requests': [request.Request._from_dict(i['request']) for i in interactions], 
        'responses': [i['response'] for i in interactions], 
    }

def migrate_json(in_fp, out_fp):
    data = json.load(in_fp)
    interactions = _migrate(data)
    out_fp.write(serialize(interactions, jsonserializer))


def _list_of_tuples_to_dict(fs):
    return dict((k, v) for k, v in fs[0])


def migrate_yml(in_fp, out_fp):
    data = yaml.load(preprocess_yaml(in_fp.read()), Loader=Loader)
    for i in range(len(data)):
        data[i]['request']['headers'] = _list_of_tuples_to_dict(data[i]['request']['headers'])
    interactions = _migrate(data)
    out_fp.write(serialize(interactions, yamlserializer))


def migrate(file_path, migration_fn):
    # because we assume that original files can be reverted
    # we will try to copy the content. (os.rename not needed)
    with tempfile.TemporaryFile(mode='w+') as out_fp:
        with open(file_path, 'r') as in_fp:
            migration_fn(in_fp, out_fp)
        with open(file_path, 'w') as in_fp:
            out_fp.seek(0)
            shutil.copyfileobj(out_fp, in_fp)


def try_migrate(path):
    if path.endswith('.json'):
        migrate(path, migrate_json)
        return True
    elif path.endswith('.yaml') or path.endswith('.yml'):
        migrate(path, migrate_yml)
        return True
    return False


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Please provide path to cassettes directory or file. "
                         "Usage: python -m vcr.migration PATH")

    path = sys.argv[1]
    if not os.path.isabs(path):
        path = os.path.abspath(path)
    files = [path]
    if os.path.isdir(path):
        files = (os.path.join(root, name)
                 for (root, dirs, files) in os.walk(path)
                 for name in files)
    for file_path in files:
            migrated = try_migrate(file_path)
            status = 'OK' if migrated else 'FAIL'
            sys.stderr.write("[{0}] {1}\n".format(status, file_path))
    sys.stderr.write("Done.\n")

if __name__ == '__main__':
    main()
