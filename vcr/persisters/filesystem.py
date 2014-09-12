import os


class FilesystemPersister(object):
    @classmethod
    def write(cls, cassette_path, data):
        dirname, filename = os.path.split(cassette_path)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname)
        with open(cassette_path, 'w') as f:
            f.write(data)
