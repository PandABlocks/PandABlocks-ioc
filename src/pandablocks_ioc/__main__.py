import logging

import click
from pandablocks.asyncio import AsyncioClient

from pandablocks_ioc._pvi import set_overwrite_bobfiles
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
@click.option(
    "--overwrite-bobfiles",
    default=False,
    is_flag=True,
    help="Overwrite .bob files if already present.",
)
@click.version_option()
@click.pass_context
def cli(ctx, log_level: str, overwrite_bobfiles: bool):
    """PandaBlocks client library command line interface."""

    level = getattr(logging, log_level.upper(), None)
    logging.basicConfig(format="%(levelname)s:%(message)s", level=level)

    set_overwrite_bobfiles(overwrite_bobfiles)

    # if no command is supplied, print the help message
    if ctx.invoked_subcommand is None:
        click.echo(cli.get_help(ctx))


@cli.command()
@click.argument("host")
@click.argument("prefix")
@click.argument("screens_dir")
def softioc(host: str, prefix: str, screens_dir: str):
    """
    Connect to the given HOST and create an IOC with the given PREFIX.
    Create .bob files for screens in the SCREENS_DIR. Directory must exist.
    """
    create_softioc(
        client=AsyncioClient(host), record_prefix=prefix, screens_dir=screens_dir
    )


# test with: python -m pandablocks_ioc
if __name__ == "__main__":
    cli()