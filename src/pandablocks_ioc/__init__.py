from importlib.metadata import version  # noqa

from .ioc import create_softioc

__version__ = version("PandABlocks-ioc")
del version

__all__ = ["__version__", "create_softioc"]
