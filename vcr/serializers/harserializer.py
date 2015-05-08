try:
    import simplejson as json
except ImportError:
    import json

def _copy_har_headers(target, source):
    for item in source['headers']:
        key = item['name']
        value = item['value']
        if key not in target['headers']:
            target['headers'][key] = []
        target['headers'][key].append(value)

def deserialize(cassette_string):
    ret = {
        'version': 1,
        'interactions': [],
    }
    raw_data = json.loads(cassette_string)
    for data in raw_data['log']['entries']:
        request = {
            'headers': {},
            'method': data['request']['method'],
            'uri': data['request']['url'],
        }
        if 'postData' in data['request']:
            request['body'] = data['request']['text']
        else:
            request['body'] = ''
        _copy_har_headers(request, data['request'])

        response = {
            'body': {
                'string': data['response']['content']['text'],
            },
            'headers': {},
            'status': {
                'code': data['response']['status'],
                'message': data['response']['statusText'],
            },
        }
        _copy_har_headers(response, data['response'])

        ret['interactions'].append({'request': request, 'response': response})
    return ret


def serialize(cassette_dict):
    raise NotImplementedError("No HAR serializer")
