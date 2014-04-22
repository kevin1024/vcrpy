"""
Migration script for old 'yaml' and 'json' cassettes

.. warning:: Backup your cassettes files before migration.

It merges and deletes the request obsolete keys (protocol, host, port, path)
into new 'uri' key.
Usage::

    python -m vcr.migration PATH

The PATH can be path to the directory with cassettes or cassette itself
"""

from contextlib import closing
import json
import os
import re
import shutil
import sys
import tempfile


PARTS = [
    'protocol',
    'host',
    'port',
    'path',
]


def build_uri(**parts):
    return "{protocol}://{host}:{port}{path}".format(**parts)


def migrate_json(in_fp, out_fp):
    data = json.load(in_fp)
    for item in data:
        req = item['request']
        uri = {k: req.pop(k) for k in PARTS}
        req['uri'] = build_uri(**uri)
    json.dump(data, out_fp, indent=4)


def migrate_yml(in_fp, out_fp):
    migrated = False
    uri = dict.fromkeys(PARTS, None)
    for line in in_fp:
        for part in uri:
            match = re.match('\s+{}:\s(.*)'.format(part), line)
            if match:
                uri[part] = match.group(1)
                break
        else:
            out_fp.write(line)

        if None not in uri.values():  # if all uri parts are collected
            out_fp.write("    uri: {}\n".format(build_uri(**uri)))
            uri = dict.fromkeys(PARTS, None)  # reset dict
            migrated = True
    if not migrated:
        raise RuntimeError("migration failed")


def migrate(file_path, migration_fn):
    # because we assume that original files can be reverted
    # we will try to copy the content. (os.rename not needed)
    with closing(tempfile.TemporaryFile(mode='w+')) as out_fp:
        with open(file_path, 'r') as in_fp:
            migration_fn(in_fp, out_fp)
        with open(file_path, 'w') as in_fp:
            out_fp.seek(0)
            shutil.copyfileobj(out_fp, in_fp)


def try_migrate(path):
    try:  # try to migrate as json
        migrate(path, migrate_json)
    except:  # probably the file is not a json
        try:  # let's try to migrate as yaml
            migrate(path, migrate_yml)
        except:  # oops probably the file is not a cassette
            return False
    return True


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
            sys.stderr.write("[{}] {}\n".format(status, file_path))
    sys.stderr.write("Done.\n")

if __name__ == '__main__':
    main()
