from importlib.metadata import version

from .ioc import create_softioc

__version__ = version("PandABlocks-ioc")
del version

__all__ = ["__version__", "create_softioc"]
