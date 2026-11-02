import logging

import click
from pandablocks.asyncio import AsyncioClient

from pandablocks_ioc._layout import MALCOLM_PORT
from pandablocks_ioc.ioc import create_softioc

__all__ = ["cli"]


@click.group(invoke_without_command=True)
@click.option(
    "--log-level",
    default="INFO",
    type=click.Choice(
        ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"], case_sensitive=False
    ),
)
@click.version_option()
@click.pass_context
def cli(ctx, log_level: str):
    """PandaBlocks client library command line interface."""

    level = getattr(logging, log_level.upper(), None)
    logging.basicConfig(format="%(levelname)s:%(message)s", level=level)

    # if no command is supplied, print the help message
    if ctx.invoked_subcommand is None:
        click.echo(cli.get_help(ctx))


@cli.command()
@click.argument("host")
@click.argument("prefix")
@click.option(
    "--screens-dir",
    type=str,
    help=(
        "Provide an existing directory to export generated bobfiles to, if no "
        "directory is provided then bobfiles will not be generated."
    ),
)
@click.option(
    "--clear-bobfiles",
    default=False,
    is_flag=True,
    help="Clear bobfiles from the given `--screens-dir` before generating new ones.",
)
@click.option(
    "--malcolm-port",
    default=MALCOLM_PORT,
    show_default=True,
    type=int,
    help="Port of the PandA web GUI's Malcolm server, used for block layout records.",
)
@click.option(
    "--no-layout",
    default=False,
    is_flag=True,
    help="Do not create block layout records.",
)
def softioc(
    host: str,
    prefix: str,
    screens_dir: str,
    clear_bobfiles: bool,
    malcolm_port: int,
    no_layout: bool,
):
    """
    Connect to the given HOST and create an IOC with the given PREFIX.
    """

    if clear_bobfiles and not screens_dir:
        raise ValueError("--clear-bobfiles passed in without a --screens-dir")

    create_softioc(
        client=AsyncioClient(host),
        record_prefix=prefix,
        screens_dir=screens_dir,
        clear_bobfiles=clear_bobfiles,
        malcolm_port=None if no_layout else malcolm_port,
    )


if __name__ == "__main__":
    cli()
