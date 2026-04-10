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
    log_level: Annotated[str, Option(help="Log level")]="INFO",
    silent: Annotated[bool, Option(help="Flag to suppress printing messages to console.")] = False,
    use_region: Annotated[Path, Option(help="")]=None,
    load_data:  Annotated[bool, Option(help="")]=True,
    overwrite: common.OVERWRITE_FLAG = False,
    cleanup: common.CLEANUP_FLAG = False,
    fail_on_warn:  Annotated[bool, Option(help="Flag to halt program execution when a warning is generated")]=False,
    ):
    context.obj = common.GlobalConfiguration(
        log_file, log_level, silent, overwrite, cleanup, 
        region_directory=use_region, import_data=load_data, fail_on_warn=fail_on_warn
    )
    # print(context.obj)

if __name__ == "__main__":
    app()
