import os
import yaml

# Use the libYAML versions if possible
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

def load_cassette(cassette_path):
    return yaml.load(open(cassette_path), Loader=Loader)

def save_cassette(cassette_path, data):
    #TODO: safe overwrite using tmpfile
    dirname, filename = os.path.split(cassette_path)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    with open(cassette_path, 'w') as cassette_file:
        cassette_file.write(yaml.dump(data, Dumper=Dumper))
