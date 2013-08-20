from .persisters.filesystem import FilesystemPersister

def load_cassette(cassette_path, serializer):
    return serializer.load(cassette_path)

def save_cassette(cassette_path, requests, responses, serializer):
    data = serializer.dumps(requests, responses)
    FilesystemPersister.write(cassette_path, data)
