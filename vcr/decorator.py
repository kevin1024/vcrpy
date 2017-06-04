from functools import wraps
from config import VCR
import os


def use_cassette(vcr=VCR(), path='fixtures/vcr_cassettes/', **kwargs):
    """
    Usage:
       @use_cassette()  # the default path will be fixtures/vcr_cassettes/foo.yaml
       def foo(self):
           ...

       @use_cassette(path='fixtures/vcr_cassettes/synopsis.yaml', record_mode='one')
       def foo(self):
           ...
    """

    def decorator(func):
        @wraps(func)
        def inner_func(*args, **kw):
            if os.path.isabs(path):
                file_path = path
            else:
                file_path = os.path.join(os.path.split(func.func_code.co_filename)[0], path)

            if not os.path.splitext(file_path)[1]:
                serializer = kwargs.get('serializer', vcr.serializer)
                file_path = os.path.join(file_path, '{0}.{1}'.format(func.func_name.lower(), serializer))

            with vcr.use_cassette(file_path, **kwargs):
                return func(*args, **kw)

        return inner_func

    return decorator
