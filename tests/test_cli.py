import subprocess
import sys

from pandablocks_ioc import __version__


def test_cli_version():
    cmd = [sys.executable, "-m", "pandablocks_ioc", "--version"]
    assert subprocess.check_output(cmd).decode().strip() == __version__
