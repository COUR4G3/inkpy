import os
import sys

import click

from ..parser import InkParser


@click.command()
@click.argument(
    "input",
    type=click.File("r", encoding="utf-8-sig"),
    default="-",
)
@click.argument(
    "output",
    type=click.Path(dir_okay=False, readable=False, writeable=True, allow_dash=True),
)
@click.option("-p", "--play", is_flag=True, help="Play mode")
def compile(input, output=None, play=False):
    """Compile ink into precompiled JSON."""
    if not output:
        if input.name and input.name != "-":
            name = os.path.basename(input.name)
            output = f"{os.path.splitext(name)[0]}.json"
        else:
            output = "-"

    parser = InkParser()
    with click.open_file(output, "w", encoding="utf-8-sig") as output:
        parser.parse(input)


def main(as_module=False):  # pragma: nocover
    prog_name = as_module and "python -m inkpy.compile" or sys.argv[0]
    compile.main(sys.argv[1:], prog_name=prog_name)


if __name__ == "__main__":
    main(as_module=True)
