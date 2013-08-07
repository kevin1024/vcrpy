import tempfile
import os
import yaml

# Use the libYAML versions if possible
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

def _secure_write(path, contents):
    """
    We'll overwrite the old version securely by writing out a temporary
    version and then moving it to replace the old version
    """
    dirname, filename = os.path.split(path)
    fd, name = tempfile.mkstemp(dir=dirname, prefix=filename)
    with os.fdopen(fd, 'w') as fout:
        fout.write(contents)
        os.rename(name, path)

def load_cassette(cassette_path):
    return yaml.load(open(cassette_path), Loader=Loader)

def save_cassette(cassette_path, data):
    dirname, filename = os.path.split(cassette_path)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    _secure_write(cassette_path, yaml.dump(data, Dumper=Dumper))
