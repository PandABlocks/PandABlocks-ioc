<<<<<<< before updating
import sys
from .ioc import create_softioc

if sys.version_info < (3, 8):
    from importlib_metadata import version  # noqa
else:
    from importlib.metadata import version  # noqa

__version__ = version("pandablocks-ioc")
del version
=======
from ._version import __version__
>>>>>>> after updating

__all__ = ["__version__", "create_softioc"]
