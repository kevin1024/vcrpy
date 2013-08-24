import tempfile
import os


class FilesystemPersister(object):
    @classmethod
    def _secure_write(cls, path, contents):
        """
        We'll overwrite the old version securely by writing out a temporary
        version and then moving it to replace the old version
        """
        dirname, filename = os.path.split(path)
        fd, name = tempfile.mkstemp(dir=dirname, prefix=filename)
        with os.fdopen(fd, 'w') as fout:
            fout.write(contents)
            os.rename(name, path)

    @classmethod
    def write(cls, cassette_path, data):
        dirname, filename = os.path.split(cassette_path)
        if dirname and not os.path.exists(dirname):
            os.makedirs(dirname)
        cls._secure_write(cassette_path, data)
