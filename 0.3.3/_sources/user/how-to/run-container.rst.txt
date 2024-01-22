Run in a container
==================

Pre-built containers with PandABlocks-ioc and its dependencies already
installed are available on `Github Container Registry
<https://ghcr.io/pandablocks/pandablocks-ioc>`_.

Starting the container
----------------------

To pull the container from github container registry run::

    $ docker run ghcr.io/pandablocks/pandablocks-ioc --version

This will pull the latest release. To get a different release, append the
version number to the end::

    $ docker run ghcr.io/pandablocks/pandablocks-ioc:0.2.1 --version