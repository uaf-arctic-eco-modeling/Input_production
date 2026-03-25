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
import xarray as xr

# from .. import cdsapi_tools
from .. datasources import era5_daily
from .. import logger

HELP = """Tools to download data"""

app = Typer(help=HELP, no_args_is_help=True)

NAME = 'Download'

@app.command()
def ERA5_daily(
        where: Annotated[Path, Argument(help="location to save final files to")],
        temp_dir: Annotated[Path, Option(help="location to save downloaded files to")]=None,
        years: Annotated[list[int], Option(help="years")]=None,
        years_as_range: Annotated[bool, Option(help="Flag to use years as range. Only check if 2 years are provided to --years")]=False,
        overwrite: Annotated[bool, Option(help="Flag to overwrite existing data")]=True,
        cleanup: Annotated[bool, Option(help="Flag to cleanup downloads by removing them")]=False,
        log_file: Annotated[Path, Option(help="path to logger file")]=None,
    ):
    """Downloads ERA5 daily data from ECMWF. This is a slow process.
    """
    overwrite = False
    cleanup = False
    log = logger.Logger(verbose_levels=logger.INFO)

    if years is None:
        years = range(1940,2026)
    
    if len(years) == 2 and years_as_range:
        years = range(years[0], years[1]+1)


    if temp_dir is None:
        temp_dir = where

    log.info(f'Processing years: {years}')

    log.info(f'Downloading from { era5_daily.COLLECTION_ID }.')
    for year in years:
        
        for variable in era5_daily.API_VARIABLES:
            yearly_files = []
            api_var = era5_daily.API_VARIABLES[variable]['name']
            save_to_final = where/f'{year}-{api_var}.nc'
            log.info(f'.. Downloading {variable} for {year}.')
            if save_to_final.exists() and not overwrite:
                log.info(f'.... Yearly file exists, download skipped.')
            for month in range(1, 13):
                log.info(f'.... Downloading partial {variable} for {year}-{month:02}.')
                file, status = era5_daily.download_variable_for_year_month(
                    where, variable, year, month, overwrite=False
                )
                if status == 'skipped':
                    log.info(f'...... File exists, download skipped.')
                elif status == 'complete':
                    log.info(f'...... Download complete.')
                else:
                    log.error(f'...... Download failed. exiting')
                    return # correct action?
                yearly_files.append(file)
            log.info(f'.... Merging partials to {save_to_final.name}')
            datasets = [xr.open_dataset(f) for f in yearly_files]
            final = xr.concat(datasets, dim='valid_time')
            final.to_netcdf(save_to_final)
            final.close()
            [ds.close() for ds in datasets]
            if cleanup:
                log.info(f'.... Cleanup: removing partials {[f.name for f in yearly_files]}.')
                [file.unlink(file) for file in yearly_files]
            

    log.info('Complete!')
    if log_file:
        log.write(log_file)