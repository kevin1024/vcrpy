import yaml

# Use the libYAML versions if possible
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


def load(cassette_path):
    data = yaml.load(open(cassette_path), Loader=Loader)
    requests = [r['request'] for r in data]
    responses = [r['response'] for r in data]
    return requests, responses


def dumps(requests, responses):
    data = ([{
        'request': request,
        'response': response,
    } for request, response in zip(requests, responses)])
    return yaml.dump(data, Dumper=Dumper)
