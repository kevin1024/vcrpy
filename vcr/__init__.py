from config import VCR

default_vcr = VCR()


def use_cassette(path, **kwargs):
    return default_vcr.use_cassette(path, **kwargs)
