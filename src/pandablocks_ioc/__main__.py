from argparse import ArgumentParser

from . import __version__

__all__ = ["main"]


# TODO: Proper Argument parser
def main(args=None):
    parser = ArgumentParser()
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(args)


# test with: python -m pandablocks_ioc
if __name__ == "__main__":
    main()
