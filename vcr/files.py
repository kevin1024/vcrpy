from __future__ import with_statement
import os
import yaml


def load_cassette(cassette_path):
    try:
        return yaml.load(open(cassette_path))
    except IOError:
        return None


def save_cassette(cassette_path, cassette):
    dirname, filename = os.path.split(cassette_path)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    with open(cassette_path, 'wc') as cassette_file:
        cassette_file.write(cassette.serialize())
