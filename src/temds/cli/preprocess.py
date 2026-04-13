"""
CLI tools for preprocessing
---------------------------

TODO:
    - better configuration of output file name
    - options for save parameters
"""
from pathlib import Path

from typer import Typer, Argument, Option, Context
from typing import Annotated

import xarray as xr
from joblib import Parallel, delayed, parallel_config


from .. import datasources
from ..region.region import Region
from . import common
from .region import import_data

HELP = """Tools to preprocess data"""

app = Typer(help=HELP, no_args_is_help=True)

NAME = 'Preprocess'

@app.command()
def era5_daily(
        context: Context,
        destination: common.DESTINATION_DIR,
        source: common.SOURCE_DIR,
        years: common.ERA5_YEARS = None,
        years_as_range: common.YEAR_RANGE_FLAG =False,
        # overwrite: common.OVERWRITE_FLAG = True,
        # cleanup: common.CLEANUP_FLAG = False,
    ):
    """Preprocesses downloaded ERA5 daily data. Preprocessed data will be
    formatted to be read as a YearlyDataset.
    """
    log = context.obj.log
    overwrite = context.obj.overwrite
    cleanup = context.obj.cleanup


    destination = Path(destination)

    downloads = source
    downloads = Path(downloads)

    years = common.years_as_range_check(years, years_as_range, [1940,2025])
    
    log.info(f'Running for {years}')

    for year in years:
        log.info(f'Preprocessing year: {year}')

        yearly_files = list(downloads.glob(f'*{year}*.nc'))
        log.info(f'.. Files found {[f.name for f in yearly_files]}.')

        yearly_data = [xr.open_dataset(file) for file in yearly_files]
        log.info(f'.. Merging')
        merged = datasources.era5_daily.merge_for_year(year, yearly_data)

        save_to = destination/f'daily-ERA5-{year}.nc'
        log.info(f'.. Saving to {save_to}.')
        merged.save(save_to, overwrite=overwrite)

        [ds.close() for ds in yearly_data]
        if cleanup:
            log.info(f'.. Cleanup. removing {[f.name for f in yearly_files]}.')
            [file.unlink(file) for file in yearly_files]
    log.info('Complete!')

@app.command()
def cmip6_daily(
        context: Context,
        destination: common.DESTINATION_DIR,
        source: common.SOURCE_DIR,
        years: Annotated[tuple[int, int], Argument(help="Start and end of years to download data for. Will default to full range of experiment provided")] = None,
        source_match: Annotated[str, Option(help=f"")] = '*.nc',
        name: Annotated[str, Option(help=f"")] = 'cmpi6',

        # region_directory: Annotated[Path, Option(help='region folder with manifest.yml, this will supersede the default destination path')]= None,

        # overwrite: common.OVERWRITE_FLAG = False,
        # cleanup: common.CLEANUP_FLAG = False
    ):
    log = context.obj.log
    overwrite = context.obj.overwrite
    cleanup = context.obj.cleanup
    parallel = context.obj.parallel
    n_process = context.obj.get_n_process()
    data = []

    start_year = None
    end_year = None
    if years is None:
        for var_file in Path(source).glob(source_match):
            ds = xr.open_dataset(var_file)
            start_year = ds.time.values[0].year
            end_year = ds.time.values[-1].year
    else:
        start_year = years[0]
        end_year = years[1]
    log.info(f'Processing data from {start_year} to {end_year}')



    from_cmip6 = lambda year: datasources.dataset.YearlyDataset.from_cmip6(
        year, source,file_name_match=source_match
    )
    with parallel_config(backend="loky", n_jobs=n_process, verbose=1):
        data = Parallel()(
            delayed(from_cmip6)(year) for year in range(start_year, end_year+1)
        )

    # for year in range(start_year, end_year+1):
    #     log.info(f'.. processing {year}')
    #     data.append(   
    #         datasources.dataset.YearlyDataset.from_cmip6(
    #             year, 
    #             source,
    #             file_name_match=source_match
    #         )
    #     )
    # log.info(f'saving')
    data = datasources.timeseries.YearlyTimeSeries(data)

    try: 
        if context.obj.region:
            log.info('Preprocessing to region, Vapo not being calculated.')
            context.obj.runtime_data['source'] = data
            import_data(context, None, None, name)
        else:
            destination_format = name+'-{year}.nc'
            data.save(destination, destination_format, overwrite=overwrite)
    except FileExistsError:
        log.error('Output files exist. Cannot save unless --overwrite is passed.')
        return
    log.info('Preprocess cmip6-daily complete!')



@app.command()
def worldclim(
        context: Context,
        destination: common.DESTINATION_FILE,
        source: common.SOURCE_DIR,
        extent_file: Annotated[Path, Argument(help="path to extent raster. used to pull extent at resolution")],
        # name: Annotated[str, Option(help=f"")] = 'worldclim',
    ):
    log = context.obj.log
    overwrite = context.obj.overwrite
    cleanup = context.obj.cleanup
    parallel = context.obj.parallel
    n_process = context.obj.get_n_process()

    if context.obj.region:
        extent_file = context.obj.region_directory/'mask.tif'
        destination = context.obj.region_directory/'worldclim.nc'

    data = datasources.dataset.TEMDataset.from_worldclim(
            source,
            download=False, 
            extent_raster=extent_file, 
            logger=log,
    )

    try: 
        data.save(destination, overwrite=overwrite)
    except FileExistsError:
        log.error('Output files exist. Cannot save unless --overwrite is passed.')
        return
    log.info('Preprocess worldclim complete!')