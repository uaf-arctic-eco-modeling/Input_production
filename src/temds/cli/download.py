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

from typer import Typer, Argument, Option, Context
from typing import Annotated
import xarray as xr
import cftime

# from .. import cdsapi_tools
from ..datasources import era5_daily, cmip6
from ..region.region import Region
from .. import logger
from .. import climate_variables 
from .. import pangeo_tools

from joblib import Parallel, delayed, parallel_config

from . import common

HELP = """Tools to download data"""

app = Typer(help=HELP, no_args_is_help=True)

NAME = 'Download'



@app.command()
def ERA5_daily(
        context: Context,
        destination: common.DESTINATION_DIR,
        years: common.ERA5_YEARS=None,
        years_as_range: common.YEAR_RANGE_FLAG =False,
        # overwrite: common.OVERWRITE_FLAG = True,
        # cleanup: common.CLEANUP_FLAG = False,
    ):
    """Downloads ERA5 daily data from ECMWF. This is a slow process.
    """
    log = context.obj.log
    overwrite = context.obj.overwrite
    cleanup = context.obj.cleanup
    # parallel = context.obj.parallel
    # n_process = context.obj.n_process


    years = common.years_as_range_check(years, years_as_range, [1940,2025])
    

    log.info(f'Processing years: {years}')
    # return

    log.info(f'Downloading from { era5_daily.COLLECTION_ID }.')
    for year in years:
        
        for variable in era5_daily.API_VARIABLES:
            yearly_files = []
            api_var = era5_daily.API_VARIABLES[variable]['name']
            save_to_final = destination/f'{year}-{api_var}.nc'
            log.info(f'.. Downloading {variable} for {year}.')
            if save_to_final.exists() and not overwrite:
                log.info(f'.... Yearly file exists, download skipped.')
            # client, requests = era5_daily.submit_variable_year(variable, year)

            # for date in xr.date_range(f'{year}-01-01', f'{year}-12-31'):
            #     month = date.month
            #     day = date.day
            #     log.info(f'.... Downloading partial {variable} for {year}-{month:02}-{day:02}.')
            #     file, status = era5_daily.download_variable_for_date(
            #         destination, variable, date, overwrite=False
            #     )
            #     if status == 'skipped':
            #         log.info(f'...... File exists, download skipped.')
            #     elif status == 'complete':
            #         log.info(f'...... Download complete.')
            #     else:
            #         log.error(f'...... Download failed. exiting')
            #         return # correct action?
            #     yearly_files.append(file)

            def download_helper(date):
                month = date.month
                day = date.day
                log.info(f'.... Downloading partial {variable} for {year}-{month:02}-{day:02}.')
                file, status = era5_daily.download_variable_for_date(
                    destination, variable, date, overwrite=False
                )
                if status == 'skipped':
                    log.info(f'...... File exists, download skipped.')
                elif status == 'complete':
                    log.info(f'...... Download complete.')
                else:
                    log.error(f'...... Download failed. exiting')
                    raise IOError('aaaaa do something')
                return file



            with parallel_config(backend="loky", n_jobs=context.obj.get_n_process(), verbose=1):
                yearly_files = Parallel()(
                    delayed(download_helper)(date) for date in xr.date_range(
                        f'{year}-01-01', f'{year}-12-31'
                    )
                )


            log.info(f'.... Merging partials to {save_to_final.name}')
            datasets = [xr.open_dataset(f) for f in sorted(yearly_files)]
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
        context: Context,
        destination: common.DESTINATION_DIR,
        experiment: Annotated[str, Argument(help=f"Name of CMIP6 experiment from {cmip6.EXPERIMENTS}")],
        source_model: Annotated[str, Argument(help="Name of CMIP6 model that provides daily data (i.e. CESM2)")],
        years: Annotated[tuple[int, int], Argument(help="Start and end of years to download data for. Will default to full range of experiment provided")] = None,
        # start_year: Annotated[int, Option(help="Start year to save data for.")] = None,
        # end_year: Annotated[int, Option(help="End year to save data for.")] = None,
        ensemble: Annotated[str, Option(help=f"CMIP6 ensemble/member_id (i.e. {cmip6.DEFAULT_ENSEMBLE})")] = cmip6.DEFAULT_ENSEMBLE ,
        region: Annotated[Path, Option(help=f"")] = None
    ):
    """download cmip6 daily data
    
    Note on `years`
        - For historical experiments these values must be between 1850 and 2014 inclusive.
        - For projected experiments these values must be between 2015 and 2100 inclusive.
        - The start year must be less than or equal to end year
        - When not provided values will default to the appropriate minimum or maximum value. 

    
    """
    log = context.obj.log

    if experiment not in cmip6.EXPERIMENTS:
        log.error(f'bad experiment try one of {cmip6.EXPERIMENTS} ')
        return
    


    start_year, end_year = years if years else (None, None)
    if experiment == 'historical':
        start_year = 1901 if start_year is None else start_year
        end_year = 2014 if end_year is None else end_year
        if start_year < 1850:
            log.error(f"Start year must be greater than or equal to  1850 for historical experiments. Was given {start_year}.")
            return
        if start_year > 2014:
            log.error(f"End year must be less than or equal to than 2014 for historical experiments. Was given {end_year}.")
            return

    else:
        start_year = 2016 if start_year is None else start_year
        end_year =  2100 if end_year is None else end_year
        if start_year < 2015:
            log.error(f"Start year must be greater than or equal to  2015 for projected (ssp) experiments. Was given {start_year}.")
            return
        if start_year > 2100:
            log.error(f"End year must be less than or equal to than 2100 for projected (ssp) experiments. Was given {end_year}.")
            return
    if start_year > end_year:
        log.error(f"Start year must be less than or equal to End year. Start year was {start_year}, and end year {end_year}.")
        return
    log.info(f'For years {start_year} - {end_year}')
    time_bounds = (
        cftime.DatetimeNoLeap(start_year, 1, 1),
        cftime.DatetimeNoLeap(end_year+1, 1, 1)
    )
    log.info(f'Searching catalog for daily {source_model}, {experiment}, {ensemble}')
    items = cmip6.search_pangeo(source_model, experiment, ensemble)
    log.info(f'.. Found {len(items)} items.')

    spatial_bounds = (0, 30, 360, 90)
    if region:
        area = Region.from_directory(region)

        spatial_bounds = area.get_extent(4326, 1)
        spatial_bounds[0]+=360
        spatial_bounds[2]+=360
        spatial_bounds = tuple(spatial_bounds)

    log.info(f'Target bounds are {spatial_bounds}')
    for row in items.index:
        meta = items.loc[row].to_dict() 
        log.info(
            f"Downloading {meta['source_id']}-{meta['experiment_id']}-{meta['variable_id']}"
        )
        save_to = destination/f"cmip6-day-{meta['source_id']}-{meta['experiment_id']}-{meta['variable_id']}.nc"
        log.info(f'.. saving to {save_to}')
        if not save_to.exists():
            ds = pangeo_tools.download(
                save_to,
                meta['zstore'], 
                time_bounds, 
                spatial_bounds,
                zlib= True, complevel= 9 
            )
            ds.close()
    log.info('Complete!')