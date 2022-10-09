import yaml

# Use the libYAML versions if possible
try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Dumper, Loader


def deserialize(cassette_string):
    return yaml.load(cassette_string, Loader=Loader)


def serialize(cassette_dict):
    return yaml.dump(cassette_dict, Dumper=Dumper)
