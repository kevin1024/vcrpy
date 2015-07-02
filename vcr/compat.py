try:
    from unittest import mock
except ImportError:
    import mock

try:
    import contextlib
except ImportError:
    import contextlib2 as contextlib
else:
    if not hasattr(contextlib, 'ExitStack'):
        import contextlib2 as contextlib

import collections
if not hasattr(collections, 'Counter'):
    import backport_collections as collections

__all__ = ['mock', 'contextlib', 'collections']
