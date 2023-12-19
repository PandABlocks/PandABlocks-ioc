PandABlocks-ioc
===========================

|code_ci| |docs_ci| |coverage| |pypi_version| |license|

A softioc to control a `PandABlocks-FPGA <https://github.com/PandABlocks/PandABlocks-FPGA>`_.

============== ==============================================================
PyPI           ``pip install PandABlocks-ioc``
Source code    https://github.com/PandABlocks/PandABlocks-ioc
Documentation  https://PandABlocks.github.io/PandABlocks-ioc
Releases       https://github.com/PandABlocks/PandABlocks-ioc/releases
============== ==============================================================

To run the ioc:

.. code-block:: text

    $ python -m pandablocks-ioc softioc <pandabox host> <pv prefix> --screens-dir=<directory to output bobfiles> --clear-bobfiles

|

PVs will be available for all the values shown on the `web client <https://github.com/PandABlocks/PandABlocks-webcontrol>`_:

.. code-block:: text

    $ caget PANDA:CALC1:INPA
    PANDA:CALC1:INPA               ZERO

..  image:: https://raw.githubusercontent.com/PandABlocks/PandABlocks-ioc/main/docs/images/webui_calc1.png
   :width: 300

|

On start-up the ioc will use `PVI <https://github.com/epics-containers/pvi>`_ to generate bobfiles for viewing the PVs in phoebus:

..  image:: https://raw.githubusercontent.com/PandABlocks/PandABlocks-ioc/main/docs/images/phoebus_calc1.png
   :width: 34%
..  image:: https://raw.githubusercontent.com/PandABlocks/PandABlocks-ioc/main/docs/images/screen_index.png
   :width: 64%


.. |code_ci| image:: https://github.com/PandABlocks/PandABlocks-ioc/actions/workflows/code.yml/badge.svg?branch=main
    :target: https://github.com/PandABlocks/PandABlocks-ioc/actions/workflows/code.yml
    :alt: Code CI

.. |docs_ci| image:: https://github.com/PandABlocks/PandABlocks-ioc/actions/workflows/docs.yml/badge.svg?branch=main
    :target: https://github.com/PandABlocks/PandABlocks-ioc/actions/workflows/docs.yml
    :alt: Docs CI

.. |coverage| image:: https://codecov.io/gh/PandABlocks/PandABlocks-ioc/branch/main/graph/badge.svg
    :target: https://codecov.io/gh/PandABlocks/PandABlocks-ioc
    :alt: Test Coverage

.. |pypi_version| image:: https://img.shields.io/pypi/v/PandABlocks-ioc.svg
    :target: https://pypi.org/project/PandABlocks-ioc
    :alt: Latest PyPI version

.. |license| image:: https://img.shields.io/badge/License-Apache%202.0-blue.svg
    :target: https://opensource.org/licenses/Apache-2.0
    :alt: Apache License

..
    Anything below this line is used when viewing README.rst and will be replaced
    when included in index.rst

See https://PandABlocks.github.io/PandABlocks-ioc for more detailed documentation.
