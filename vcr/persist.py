from .persisters.filesystem import FilesystemPersister
from .serializers.yamlserializer import YamlSerializer
from .serializers.jsonserializer import JSONSerializer

def _get_serializer_cls(serializer):
    serializer_cls = {
        'yaml': YamlSerializer,
        'json': JSONSerializer,
    }.get(serializer)
    if not serializer_cls:
        raise ImportError('Invalid serializer %s' % serializer)
    return serializer_cls

def load_cassette(cassette_path, serializer):
    serializer_cls = _get_serializer_cls(serializer)
    return serializer_cls.load(cassette_path)
    
def save_cassette(cassette_path, requests, responses, serializer):
    serializer_cls = _get_serializer_cls(serializer)
    data = serializer_cls.dumps(requests, responses)
    FilesystemPersister.write(cassette_path, data)
