import sys
from pathlib import Path

from typer import Typer, Context, Argument, Option
from typing import Annotated

from . import download
from . import preprocess
from . import region
from . import common

from ..__init__ import __version__

HELP = """Main CLI entry point for TEMDS tools"""

app = Typer(help=HELP, no_args_is_help=True)
app.add_typer(download.app, name='download')
app.add_typer(preprocess.app, name='preprocess')
app.add_typer(region.app, name='region')

def version_callback(arg):
    if arg:
        print(__version__)
        sys.exit(0)


@app.callback()
def main(
    context: Context,
    version: Annotated[bool,Option(callback=version_callback, is_eager=True)] = False,
    log_file: Annotated[Path, Option(help="Optional path to save log to")]=None,
    silent: Annotated[bool, Option(help="Flag to suppress printing messages to console.")] = False
    
    ):
    context.obj = common.GlobalConfiguration(log_file, "", silent)
    # print(context.obj)

if __name__ == "__main__":
    app()
