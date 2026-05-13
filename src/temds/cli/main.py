import sys
from pathlib import Path

from typer import Typer, Context, Argument, Option
from typing import Annotated, List

from . import download
from . import preprocess
from . import region
from . import common
from . import statistics
from . import downscale
from . import export

from ..__init__ import __version__

HELP = """Main CLI entry point for TEMDS tools"""

app = Typer(help=HELP, no_args_is_help=True)
app.add_typer(region.app,     name='region')
app.add_typer(download.app,   name='download')
app.add_typer(preprocess.app, name='preprocess')
app.add_typer(statistics.app, name='statistics')
app.add_typer(downscale.app,  name='downscale')
app.add_typer(export.app,     name='export')


def version_callback(arg):
    if arg:
        print(__version__)
        sys.exit(0)


@app.callback()
def main(
    context: Context,
    version: Annotated[bool,Option(callback=version_callback, is_eager=True, help="Flags if version TEMDS version should be shown.")] = False,
    log_file: Annotated[Path, Option(help="Optional path to save log to")]=None,
    log_level: Annotated[str, Option(help="Log level. Options are: INFO, DEBUG, WARN. ERROR, or NONE}")]="INFO",
    silent: Annotated[bool, Option(help="Flag to suppress printing messages to console.")] = False,
    use_region: Annotated[Path, Option(help="Path to a directory containing a region defined by manifest.yml")]=None,
    load_all:  Annotated[bool, Option(help="Flag to load all data for a region when --use-region is provided")]=True,
    load_item:  Annotated[List[str], Option(help="Keys for items to load for region if --no-load-all is provided")]=[],
    parallel:  Annotated[bool, Option(help="Flag to enable parallel processing")]=False,
    n_process:  Annotated[int, Option(help="Number of parallel processes to use when --parallel is used")]=4,
    overwrite: common.OVERWRITE_FLAG = False,
    cleanup: common.CLEANUP_FLAG = False,
    fail_on_warn:  Annotated[bool, Option(help="Flag to halt program execution when a warning is generated")]=False,
    ):
    """Callback for cli interface. Configures context.obj

    Parameters
    ----------
    see above.
    """
    load_data = []
    if load_all and load_item==[]:
        load_data = None # none will force load all in region constructor
    else:
        load_data = load_item

    context.obj = common.GlobalConfiguration(
        log_file, log_level, silent, overwrite, cleanup, 
        parallel=parallel, n_process=n_process,
        region_directory=use_region, import_data=load_data, fail_on_warn=fail_on_warn
    )
    # print(context.obj)

if __name__ == "__main__":
    app()
