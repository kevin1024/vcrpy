from config import VCR

default_vcr = VCR()


# Also, make a 'load' function available
def use_cassette(path, **kwargs):
    return default_vcr.use_cassette(path, **kwargs)
