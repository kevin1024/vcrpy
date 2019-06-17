from unittest import mock

try:
    import contextlib
except ImportError:
    import contextlib2 as contextlib
else:
    if not hasattr(contextlib, 'ExitStack'):
        import contextlib2 as contextlib

__all__ = ['mock', 'contextlib']
