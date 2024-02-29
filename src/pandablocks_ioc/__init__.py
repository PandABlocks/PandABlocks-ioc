from .ioc import create_softioc

from importlib.metadata import version  # noqa

__version__ = version("pandablocks-ioc")
del version

__all__ = ["__version__", "create_softioc"]
