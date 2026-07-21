"""
CLI tools for preprocessing
---------------------------

TODO:
    - better configuration of output file name
    - options for save parameters
"""
from pathlib import Path
import sys

from typer import Typer, Argument, Option, Context
from typing import Annotated, List

import xarray as xr
import numpy as np
from joblib import Parallel, delayed, parallel_config


from .. import datasources 
from ..datasources import cmip6
from ..region.region import Region
from ..region.mask import Mask
from ..region.manifest import Manifest
from . import common
from .region import import_data
from .. import climate_variables
from .. import era5_corr


HELP = """Tools to preprocess data"""

app = Typer(help=HELP, no_args_is_help=True)

NAME = 'Preprocess'

@app.command()
def era5_daily(
        context: Context,
        destination: common.DESTINATION_DIR,
        source: common.SOURCE_DIR,
        years: Annotated[tuple[int, int], Argument(help="Range of years to preprocess ERA5 daily data for.")] = None
        # years: common.ERA5_YEARS = None,
        # years_as_range: common.YEAR_RANGE_FLAG = False,
        # overwrite: common.OVERWRITE_FLAG = True,
        # cleanup: common.CLEANUP_FLAG = False,
    ):
    """This command preprocesses downloaded ERA5 daily data. Preprocessed data 
    will be formatted to be read as a YearlyDataset.
    """
    log = context.obj.log
    overwrite = context.obj.overwrite
    cleanup = context.obj.cleanup
    log.info('Starting preprocessing of ERA5-daily data')


    if context.obj.region: ## TODO suport region in this function
        destination = context.obj.region_directory / 'ERA5-'


    if destination.exists() and overwrite == False: context.obj.overwrite_disabled_exit()

    downloads = source
    downloads = Path(downloads)

    years = common.years_as_range_check(years, True, [1940,2025])
    
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
        source_match: Annotated[str, Option(help=f"bash style file name matching for finding source data to load")] = '*.nc',
        name: Annotated[str, Option(help=f"Optional name to use for output files")] = 'cmpi6',
        topo: Annotated[Path, Option(help=f"path to preprocessed tem formatted topo data")] = None,

        # region_directory: Annotated[Path, Option(help='region folder with manifest.yml, this will supersede the default destination path')]= None,

        # overwrite: common.OVERWRITE_FLAG = False,
        # cleanup: common.CLEANUP_FLAG = False
    ):
    """This command preprocesses CMIP6 daily data to use in downscaling. If topo
    is provided the variable for VAPO is calculated otherwise it is not.
    """
    log = context.obj.log
    overwrite = context.obj.overwrite
    cleanup = context.obj.cleanup
    parallel = context.obj.parallel
    n_process = context.obj.get_n_process()
    data = []
    log.info('Starting preprocessing of CMIP6 Daily data')

    if context.obj.region:
        destination = context.obj.region_directory/ name
        
    if destination.exists() and overwrite == False: context.obj.overwrite_disabled_exit()


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
        year, source, file_name_match=source_match
    )

    with parallel_config(backend="loky", n_jobs=n_process, verbose=1):
        data = Parallel()(
            delayed(from_cmip6)(year) for year in range(start_year, end_year+1)
        )

    data = datasources.timeseries.YearlyTimeSeries(data)

    try: 
        if context.obj.region:
            area = context.obj.region
            try:
                topo = datasources.dataset.TEMDataset(
                        context.obj.region_directory/'topo.nc', log
                )
                area.import_datasource('topo', topo)
            except:
                pass

            log.info('Preprocessing to region')
            context.obj.runtime_data['source'] = data
            # import_data(context, None, None, name) ## with the callback its easier to not use existing fn
            if 'topo' in context.obj.region.data:
                log.info('With VAPO')
                callback_fn = cmip6.callback_psl_to_vapo
                elevation = area.data['topo'].dataset['elevation']
            else:
                log.info('With out VAPO, no topo found')
                callback_fn = None
                elevation = None

            with parallel_config(backend="loky", n_jobs=n_process, verbose=1):
                area.import_datasource(name, data, parallel=parallel, callback=callback_fn, elevation=elevation)

            with parallel_config(backend="loky", n_jobs=n_process, verbose=1):
                context.obj.callback_export_region([name], parallel=parallel)

        else:
            destination_format = name+'-{year}.nc'
            if topo:
                log.info('Adding VAPO')
                topo = datasources.dataset.TEMdataset(topo)
                elevation = topo.dataset['elevation']
                data.dataset = cmip6.callback_psl_to_vapo(data.dataset, log, elevation=elevation)
            else:
                log.info('Skipping VAPO, no topo data')

            data.save(destination, destination_format, overwrite=overwrite)
    except FileExistsError:
        log.error('Output files exist. Cannot save unless --overwrite is passed.')
        return
    log.info('Preprocessing of CMIP6-daily data complete!')

@app.command()
def worldclim(
        context: Context,
        destination: common.DESTINATION_FILE,
        source: common.SOURCE_DIR,
        extent_file: Annotated[Path, Argument(help="Path to extent raster which is used to determine projection, extent, and resolution of data")],
        # name: Annotated[str, Option(help=f"")] = 'worldclim',
    ):
    """This command creates the worldclim climate reference dataset from raw worldclim data and an extent
    """
    log = context.obj.log
    overwrite = context.obj.overwrite
    cleanup = context.obj.cleanup
    parallel = context.obj.parallel
    n_process = context.obj.get_n_process()
    log.info('Preprocessing worldclim data.')

    if context.obj.region:
        region = context.obj.region
        destination = context.obj.region_directory/'worldclim.nc'
    else: 
        region = Region.from_mask(Mask.from_file(extent_file), logger=log)

    if destination.exists() and overwrite == False: context.obj.overwrite_disabled_exit()

    data = datasources.dataset.TEMDataset.from_worldclim(
            source,
            region,
            download=False, 
            logger=log,
            # resample_alg='bilinear'
    )

    try: 
        data.save(destination, overwrite=overwrite)
        if context.obj.region:
            man = Manifest.from_file( context.obj.region_directory/ 'manifest.yml' )
            man.add_dataset('worldclim', destination.name)
            man.to_file(context.obj.region_directory/ 'manifest.yml' )
    except FileExistsError:
        log.error('Output files exist. Cannot save unless --overwrite is passed.')
        return
    log.info('Preprocessing worldclim complete!')

@app.command()
def topo(
        context: Context,
        destination: common.DESTINATION_FILE,
        source: common.SOURCE_FILE,
        extent_file: Annotated[Path, Argument(help="path to extent raster. used to pull extent at resolution")],
        algorithm: Annotated[str, Option(help=f"Algorithm used in resampling.")] = 'average',
    ):
    """This command creates the topo data set from an input elevation dataset, and an extent
    """
    log = context.obj.log
    overwrite = context.obj.overwrite
    log.info("Starting preprocessing of topo data.")

    if context.obj.region:
        region = context.obj.region
        destination = context.obj.region_directory/'topo.nc'
    else: 
        region = Region.from_mask(Mask.from_file(extent_file))

    if destination.exists() and overwrite == False: context.obj.overwrite_disabled_exit()

    topo_ds = datasources.dataset.TEMDataset.from_topo(
        source, region, 
        overwrite=overwrite, resample_alg = algorithm, logger=log
    )
        
    topo_ds.save(destination)
    if context.obj.region:
        man = Manifest.from_file( context.obj.region_directory/ 'manifest.yml' )
        man.add_dataset('topo', 'topo.nc')
        man.to_file(context.obj.region_directory/ 'manifest.yml' )

    print('Preprocessing of topo data complete!')

@app.command()
def check_spatial_mask(
        context: Context,
        to_check: Annotated[str, Argument(help="Path of data to Check.")],
        mask: Annotated[str, Option(help="Which mask to use")] = None,
    ):
    """
    """
    #TODO: cleaun up docstrings
    #TODO: add loading mask from file
    log = context.obj.log

    mask_type = "?"
    if context.obj.region:
        region = context.obj.region
        dataset = region.data[to_check]
        mask_type = "region"
    else: 
        to_check = Path(to_check)
        if to_check.is_dir():
            dataset = datasources.timeseries.YearlyTimeSeries(to_check)
            mask_type = "ts"
        elif to_check.exists():
            dataset = datasources.dataset.TEMDataset(to_check)
            mask_type = "ds"
        else:
            log.error("Data to check does not exist")
            sys.exit()

    if mask is None:
        if 'ts' == mask_type:
            sy = dataset.start_year
            tv = list(dataset[sy].dataset.data_vars)[0]
            mask = np.isnan(dataset[sy].dataset[tv][0])
        elif 'ds' == mask_type:
            tv = list(dataset.dataset.data_vars)[0]
            mask = np.isnan(dataset.dataset[tv][0])
        elif 'region' == mask_type:
            mask = region.mask.raster.ReadAsArray()
        
        else:
            log.error('Cannot Infer mask to check')
            sys.exit(1)
    else:
        raise NotImplementedError('Mask options not implemented')

    r = dataset.check_dataset_with_nan_mask(mask)

    if r:
        log.info("The data's extent matches the mask")
    else:
        log.error("The data's extent dose not match the mask")
        sys.exit(1)

@app.command()
def check_number_days(
        context: Context,
        to_check: Annotated[str, Argument(help="Path of data to Check.")],
    ):
    """
    """
    #TODO: cleaun up docstrings
    log = context.obj.log

    n_days = 365

    if context.obj.region:
        region = context.obj.region
        dataset = region.data[to_check]
    else: 
        to_check = Path(to_check)
        if to_check.is_dir():
            dataset = datasources.timeseries.YearlyTimeSeries(to_check)
        elif to_check.exists():
            dataset = datasources.dataset.YearlyDataset(to_check)
        else:
            log.error("Data to check does not exist")
            sys.exit(1)

    r, missing = dataset.check_number_timesteps(n_days)

    if r:
        log.info("The data has correct number of days.")
    else:
        log.error("The data as incorrect number of days.")
        sys.exit(1)

@app.command()
def fill_outliers(
        context: Context,
        to_fill: Annotated[str, Argument(help="Path of data to fill.")],
        variables: Annotated[List[str], Argument(help="list of variables to downscale")] = None,

    ):
    log = context.obj.log
    parallel = context.obj.parallel
    n_process = context.obj.get_n_process()
    if variables:
        unsafe = False
        for var in variables:
            if not var in climate_variables.DOWNSCALE_SAFE:
                log.error(f'variable "{var}" is not downscale safe.')
                unsafe = True

        if unsafe:
            log.info(f'Downscale safe variables are {climate_variables.DOWNSCALE_SAFE}')
            sys.exit()
    else:
        log.warn(f'Assuming downscale safe variables are present: {climate_variables.DOWNSCALE_SAFE}')
        variables = climate_variables.DOWNSCALE_SAFE
    
    region = None
    if context.obj.region:
        region = context.obj.region
        dataset = region.data[to_fill]
    else: 
        to_fill = Path(to_fill)
        if to_fill.is_dir():
            dataset = datasources.timeseries.YearlyTimeSeries(to_fill)
        elif to_fill.exists():
            log.error("This command only supports YearlyTimeSeries Data")
            sys.exit()
        else:
            log.error("Data to check does not exist")
            sys.exit()

    start_year = dataset.start_year
    end_year = dataset.range().stop - 1

    means =  {var: dataset.calculate_daily_average(var, start_year, end_year) for var in variables}
    std_devs = {var: dataset.calculate_daily_std_dev(var, start_year, end_year) for var in variables}


    for var in variables:
        dataset.fill_outliers(var, means[var], std_devs[var], 5)

    # TODO add save options
    if region:
        region.data[to_fill] = dataset
        region_directory = context.obj.region_directory
        with parallel_config(backend="loky", n_jobs=n_process, verbose=1):
            context.obj.callback_export_region([to_fill], parallel=parallel)
    else:
        dataset.save(to_fill, overwrite=True, zlib=True, complevel=9)

@app.command()
def fill_oob(
        context: Context,
        to_fill: Annotated[str, Argument(help="Path of data to Check.")],
        variable: Annotated[str, Argument(help="list of variables to downscale")],
        bound: Annotated[int, Argument(help='lower bound')],
        which: Annotated[str, Argument(help='which bound upper or lower')],
    ):
    """fill data to have the limit at the provided bounding value
    """
    # TODO clean up cli
    log = context.obj.log
    parallel = context.obj.parallel
    n_process = context.obj.get_n_process()

    region = None
    if context.obj.region:
        region = context.obj.region
        dataset = region.data[to_fill]
    else: 
        to_fill = Path(to_fill)
        if to_fill.is_dir():
            dataset = datasources.timeseries.YearlyTimeSeries(to_fill)
        elif to_fill.exists():
            log.error("This command only supports YearlyTimeSeries Data")
            sys.exit()
        else:
            log.error("Data to check does not exist")
            sys.exit()

    dataset.fill_out_of_bounds(variable, bound, which, bound)
    # TODO add save options
    if region:
        region.data[to_fill] = dataset
        region_directory = context.obj.region_directory
        with parallel_config(backend="loky", n_jobs=n_process, verbose=1):
            context.obj.callback_export_region([to_fill], parallel=parallel)
    else:
        dataset.save(to_fill, overwrite=True, zlib=True, complevel=9)


@app.command()
def era5_corrections(
        context: Context,
        daily: Annotated[str, Argument(help="Name or Path to daily era5")],
        baseline: Annotated[str, Argument(help="Name or path to Era5 baseline")],
        reference: Annotated[int, Argument(help='Name or path to reference data(i,e worldcim)')],
        corrections: Annotated[int, Argument(help='Name or path to save corrections as ')],

    ):
    """"""
    # TODO clean up cli
    log = context.obj.log
    parallel = context.obj.parallel
    n_process = context.obj.get_n_process()
    overwrite = context.obj.overwrite

    region = None
    if context.obj.region:
        log.info('Using region from context')
        region = context.obj.region
        daily_ds = region.data[daily]
        baseline_ds = region.data[baseline]
        reference_ds = region.data[reference]
    else: 
        log.info('Using data from paths')
        daily_ds = datasources.timeseries.YearlyTimeSeries(daily)
        baseline_ds = datasources.dataset.TEMDataset(baseline)
        reference_ds = datasources.dataset.TEMDataset(reference)

    era5_corr_list = []
    for year in daily_ds.range():
        log.info(f'Correcting year {year}')
        temp = era5_corr.calc_era5_corrections(
                baseline_ds, 
                reference_ds, 
                daily_ds[year]
        )
        temp.rio.set_spatial_dims(x_dim="x", y_dim="y", inplace=True)
        temp.rio.write_crs(daily.crs.crs, inplace=True)
        temp.rio.write_coordinate_system(inplace=True) 
        # downscaled.rio.write_transform(source.rio.transform(), inplace=True)
        era5_corr_list.append(datasources.dataset.YearlyDataset(year, temp))

    log.info('Finalizing...')
    corrections_ds = datasources.timeseries.YearlyTimeSeries(era5_corr_list)
    if context.obj.region:
        context.obj.region.data['era5-corr'] = corrections_ds


    log.info('Saving Results...')
    if context.obj.region:
        context.obj.callback_export_region(
            [corrections], 
            overwrite=overwrite
        ) 
    else:
        out_path = corrections
        corrections_ds.save(out_path, overwrite=overwrite)