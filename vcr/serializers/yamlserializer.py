import yaml

# Use the libYAML versions if possible
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


def deserialize(cassette_string):
    data = yaml.load(cassette_string, Loader=Loader)
    requests = [r['request'] for r in data]
    responses = [r['response'] for r in data]
    return requests, responses


def serialize(cassette_dict):
    data = ([{
        'request': request,
        'response': response,
    } for request, response in zip(
        cassette_dict['requests'],
        cassette_dict['responses']
    )])
    return yaml.dump(data, Dumper=Dumper)
