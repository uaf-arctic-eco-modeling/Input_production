"""
CLI for downloading
-------------------

TODO: 
    - era5 bounds options,
    - commands or options to submit er5 requests and let user return and download later?
"""
from pathlib import Path

from typer import Typer, Argument, Option
from typing_extensions import Annotated

# from .. import cdsapi_tools
from .. import datasources
from .. import logger

HELP = """Tools to download data"""

app = Typer(help=HELP, no_args_is_help=True)

NAME = 'Download'

@app.command()
def era5_daily(
        where: Annotated[Path, Argument(help="location to save final files to")],
        temp_dir: Annotated[Path, Option(help="location to save downloaded files to")]=None,
        years: Annotated[list[int], Option(help="years")]=None,
        log_file: Annotated[Path, Option(help="path to logger file")]=None,
    ):
    """Downloads ERA5 daily data from ECMWF. This is a slow process.
    """
    log = logger.Logger(verbose_levels=logger.INFO)

    if years is None:
        years = range(1940,2026)

    if temp_dir is None:
        temp_dir = where

    log.info(f'Downloading from { era5_daily.COLLECTION_ID }.')
    for year in years:
        
        # yearly_files = []
        for variable in era5_daily.API_VARIABLES:
            log.info(f'.. Downloading {variable} for {year}.')
            file, status = datasources.era5_daily.download_variable_for_year(
                where, variable, year, overwrite=False
            )
            if status == 'skipped':
                log.info(f'.... File exists, download skipped.')
            elif status == 'complete':
                log.info(f'.... Download complete.')
            else:
                log.error(f'.. Download failed.')
                continue # correct action?
    log.info('Complete!')
    if log_file:
        log.write(log_file)