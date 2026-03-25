"""
CLI for downloading
-------------------

TODO: 
    - era5 bounds options, cmpi6 bounds.
    - commands or options to submit er5 requests and let user return and download later?
    - better start_year end_year for cmip6 
    - cmip6 overwrite
"""
from pathlib import Path

from typer import Typer, Argument, Option
from typing_extensions import Annotated
import xarray as xr
import cftime

# from .. import cdsapi_tools
from ..datasources import era5_daily, cmip6
from .. import logger
from .. import climate_variables 
from .. import pangeo_tools

HELP = """Tools to download data"""

app = Typer(help=HELP, no_args_is_help=True)

NAME = 'Download'

@app.command()
def ERA5_daily(
        where: Annotated[Path, Argument(help="location to save final files to")],
        years: Annotated[list[int], Option(help="years")]=None,
        years_as_range: Annotated[bool, Option(help="Flag to use years as range. Only check if 2 years are provided to --years")]=False,
        overwrite: Annotated[bool, Option(help="Flag to overwrite existing data")]=True,
        cleanup: Annotated[bool, Option(help="Flag to cleanup downloads by removing them")]=False,
        log_file: Annotated[Path, Option(help="path to logger file")]=None,
        silent: Annotated[bool, Option(help="Flag to suppress printing messages to console.")] = False
    ):
    """Downloads ERA5 daily data from ECMWF. This is a slow process.
    """
    log = logger.Logger(verbose_levels=logger.INFO, write_to=log_file)
    if silent: log.suspend()

    if years is None:
        years = range(1940,2026)
    
    if len(years) == 2 and years_as_range:
        years = range(years[0], years[1]+1)


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

@app.command()
def CMIP6_daily(
        where: Annotated[Path, Argument(help="location to save final files to")],
        experiment: Annotated[str, Argument(help="")],
        source_model: Annotated[str, Argument(help="")],
        # start_year: Annotated[int, Argument(help="")],
        # end_year: Annotated[int, Argument(help="")],
        ensemble: Annotated[str, Option(help="")] = cmip6.DEFAULT_ENSEMBLE ,
        log_file: Annotated[Path, Option(help="path to logger file")]=None,
        silent: Annotated[bool, Option(help="Flag to suppress printing messages to console.")] = False
    ):
    """download cmip6 daily data"""
    log = logger.Logger(verbose_levels=logger.INFO, write_to=log_file)
    if silent: log.suspend()

    if experiment not in cmip6.EXPERIMENTS:
        log.error(f'bad experiment try one of {cmip6.EXPERIMENTS} ')
        return

    start_year = 2016
    end_year =  2101
    if experiment == 'historical':
        start_year=1901
        end_year = 2015
    log.info(f'For years {start_year} - {end_year}')
    time_bounds = (
        cftime.DatetimeNoLeap(start_year, 1, 1),
        cftime.DatetimeNoLeap(end_year+1, 1, 1)
    )

    log.info(f'Searching catalog for daily {source_model}, {experiment}, {ensemble}')
    items = cmip6.search_pangeo(source_model, experiment, ensemble)
    log.info(f'.. Found {len(items)} items.')


    spatial_bounds = (0, 30, 360, 90)
    for row in items.index:
        meta = items.loc[row].to_dict() 
        log.info(
            f"Downloading {meta['source_id']}-{meta['experiment_id']}-{meta['variable_id']}"
        )
        save_to = where/f"cmip6-day-{meta['source_id']}-{meta['experiment_id']}-{meta['variable_id']}.nc"
        print(save_to)
        if not save_to.exists():
            ds = pangeo_tools.download(
                save_to,
                meta['zstore'], 
                time_bounds, 
                spatial_bounds,
                zlib= True, complevel= 9 
            )
            ds.close()
