"""Top level API.

.. data:: __version__
    :type: str

    Version number as calculated by https://github.com/pypa/setuptools_scm
"""

from ._version import __version__
from .ioc import create_softioc

__all__ = ["__version__", "create_softioc"]
