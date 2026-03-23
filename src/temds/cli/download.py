
from pathlib import Path

from typer import Typer, Argument, Option
from typing_extensions import Annotated

from .. import cdsapi_tools
from .. import logger

HELP = """Tools to download data"""

app = Typer(help=HELP, no_args_is_help=True)

NAME = 'Download'

@app.command()
def era5_daily(
        where: Annotated[Path, Argument(help="location to save downloaded files to")],
        log_file: Annotated[Path, Option(help="path to logger file")]=None,
    ):
    log = logger.Logger(verbose_levels=logger.INFO)
    cdsapi_tools.download_era5_daily(
        where, 
        range(1940,2026), 
        cdsapi_tools.DEFAULT_BOUNDS, 
        cdsapi_tools.DEFAULT_VARIABLES, 
        logger=log
    )
    if log_file:
        log.write(log_file)