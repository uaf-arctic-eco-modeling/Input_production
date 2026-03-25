"""
CLI tools for preprocessing
---------------------------

TODO:
    - better configuration of output file name
    - options for save parameters
"""
from pathlib import Path

from typer import Typer, Argument, Option
from typing_extensions import Annotated
import xarray as xr

from .. import datasources
from .. import logger

HELP = """Tools to preprocess data"""

app = Typer(help=HELP, no_args_is_help=True)

NAME = 'Preprocess'

@app.command()
def era5_daily(
        where: Annotated[Path, Argument(help="Output file directory")],
        downloads: Annotated[Path, Option(help="Optional alternate directory where downloads are.")]=None,
        years: Annotated[list[int], Option(help="Years to preprocess, if not provided utility will attempt to process from 1940-2025")]=None,
        overwrite: Annotated[bool, Option(help="Flag to overwrite existing data")]=True,
        cleanup: Annotated[bool, Option(help="Flag to cleanup downloads by removing them")]=False,
        log_file: Annotated[Path, Option(help="Optional file to save log as")]=None,
        silent: Annotated[bool, Option(help="Flag to suppress printing messages to console.")] = False
    ):
    """Preprocesses downloaded ERA5 daily data. Preprocessed data will be
    formatted to be read as a YearlyDataset.
    """
    log = logger.Logger(verbose_levels=logger.INFO, write_to=log_file)
    if silent: log.suspend()
    
    where = Path(where)
    if downloads is None:
        downloads = where
    downloads = Path(downloads)

    if years is None:
        years = range(1940,2026)

    for year in years:
        log.info(f'Preprocessing year: {year}')

        yearly_files = list(downloads.glob(f'*{year}*.nc'))
        log.info(f'.. Files found {[f.name for f in yearly_files]}.')

        yearly_data = [xr.open_dataset(file) for file in yearly_files]
        merged = datasources.era5_daily.merge_for_year(year, yearly_data)

        save_to = where/f'daily-ERA5-{year}.nc'
        merged.save(save_to, overwrite=overwrite)
        log.info(f'.. Merge and save to {save_to}.')

        [ds.close() for ds in yearly_data]
        if cleanup:
            log.info(f'.. Cleanup: removing {[f.name for f in yearly_files]}.')
            [file.unlink(file) for file in yearly_files]
    log.info('Complete!')
    if log_file:
        log.write(log_file)
