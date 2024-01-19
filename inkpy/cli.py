import sys

import click

from .compiler.cli import compile


@click.group()
def cli():
    """Tools for inkle's ink, a scripting language for writing interactive narrative."""


cli.add_command(compile)


def main(as_module=False):  # pragma: nocover
    prog_name = as_module and "python -m inkpy" or sys.argv[0]
    cli.main(sys.argv[1:], prog_name=prog_name)


if __name__ == "__main__":
    main(as_module=True)
