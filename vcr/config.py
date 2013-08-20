from .cassette import Cassette

class VCR(object):
    def __init__(self, serializer='yaml', cassette_library_dir=None):
        self.serializer = serializer
        self.cassette_library_dir = cassette_library_dir

    def use_cassette(self, path, **kwargs):
        return Cassette.load(path, **kwargs)
