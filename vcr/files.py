import os
import yaml
from .cassette import Cassette


def load_cassette(cassette_path):
    try:
        pc = yaml.load(open(cassette_path))
        cassette = Cassette(pc)
        return cassette
    except IOError:
        return None


def save_cassette(cassette_path, cassette):
    dirname, filename = os.path.split(cassette_path)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    with open(cassette_path, 'a') as cassette_file:
        cassette_file.write(yaml.dump(cassette.serialize()))
