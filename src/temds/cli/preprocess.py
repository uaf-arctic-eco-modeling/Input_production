
from pathlib import Path

from typer import Typer, Argument, Option
from typing_extensions import Annotated

from .. import cdsapi_tools
from .. import logger

HELP = """Tools to preprocess data"""

app = Typer(help=HELP, no_args_is_help=True)

NAME = 'Download'

@app.command()
def era5_daily(
        where: Annotated[Path, Argument(help="location to save final files to")],
        downloads: Annotated[Path, Option(help="location to save downloaded files to")]=None,
        years: Annotated[list[int], Option(help="years")]=None,
        log_file: Annotated[Path, Option(help="path to logger file")]=None,
    ):
    log = logger.Logger(verbose_levels=logger.INFO)
    
    where = Path(where)
    if downloads is None:
        downloads = where
    downloads = Path(downloads)
    if years is None:
        years = range(1940,2026)
    print(years)
    for year in years:
        log.info(f'Preprocessing year: {year}')
        yearly_files = downloads.glob(f'*{year}*.nc')
        merged = cdsapi_tools.merge_yearly(year, yearly_files, cleanup = False)
        merged.save(where/f'daily-ERA5-{year}.nc', overwrite=True)

    if log_file:
        log.write(log_file)