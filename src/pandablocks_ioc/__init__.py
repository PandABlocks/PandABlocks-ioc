from importlib.metadata import version

__version__ = version("PandABlocks-ioc")
del version

__all__ = ["__version__"]
