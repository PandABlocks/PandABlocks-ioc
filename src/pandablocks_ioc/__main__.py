import logging

import click
from pandablocks.asyncio import AsyncioClient

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
@click.option("--skip-bobfile-gen-if-dir-not-empty", default=False, is_flag=True)
def softioc(
    host: str,
    prefix: str,
    screens_dir: str,
    skip_bobfile_gen_if_dir_not_empty: bool,
):
    """
    Connect to the given HOST and create an IOC with the given PREFIX.
    """
    create_softioc(
        client=AsyncioClient(host),
        record_prefix=prefix,
        screens_dir=screens_dir,
        skip_bobfile_gen_if_dir_not_empty=skip_bobfile_gen_if_dir_not_empty,
    )


# test with: python -m pandablocks_ioc
if __name__ == "__main__":
    cli()
