[![CI](https://github.com/PandABlocks/PandABlocks-ioc/actions/workflows/ci.yml/badge.svg)](https://github.com/PandABlocks/PandABlocks-ioc/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/PandABlocks/PandABlocks-ioc/branch/main/graph/badge.svg)](https://codecov.io/gh/PandABlocks/PandABlocks-ioc)
[![PyPI](https://img.shields.io/pypi/v/pandablocks-ioc.svg)](https://pypi.org/project/pandablocks-ioc)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

# PandABlocks-ioc

A softioc to control a [PandABlocks-FPGA](https://github.com/PandABlocks/PandABlocks-FPGA).

Source          | <https://github.com/PandABlocks/PandABlocks-ioc>
:---:           | :---:
PyPI            | `pip install pandablocks-ioc`
Docker          | `docker run ghcr.io/pandablocks/PandABlocks-ioc:latest`
Documentation   | <https://pandablocks.github.io/PandABlocks-ioc>
Releases        | <https://github.com/PandABlocks/PandABlocks-ioc/releases>

To run the ioc:

```text
$ python -m pandablocks-ioc softioc <pandabox host> <pv prefix> --screens-dir=<directory to output bobfiles> --clear-bobfiles
```

PVs will be available for all the values shown on the [web client](https://github.com/PandABlocks/PandABlocks-webcontrol):

```text
$ caget PANDA:CALC1:INPA
PANDA:CALC1:INPA               ZERO
```

<img src="https://raw.githubusercontent.com/PandABlocks/PandABlocks-ioc/main/docs/images/webui_calc1.png" width="300px">

On start-up the ioc will use [PVI](https://github.com/epics-containers/pvi) to generate bobfiles for viewing the PVs in phoebus:

<img src="https://raw.githubusercontent.com/PandABlocks/PandABlocks-ioc/main/docs/images/phoebus_calc1.png" width="34%">

<img src="https://raw.githubusercontent.com/PandABlocks/PandABlocks-ioc/main/docs/images/screen_index.png" width="64%">

<!-- README only content. Anything below this line won't be included in index.md -->

See <https://PandABlocks.github.io/PandABlocks-ioc> for more detailed documentation.
