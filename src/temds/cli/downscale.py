"""
CLI tools for downscaling
-------------------------

TODO:
    - better configuration of output file name
    - options for save parameters
"""
from pathlib import Path

from typer import Typer, Argument, Option, Context
from typing import Annotated, List

from joblib import parallel_config
import xarray as xr
import sys

from .. import datasources
from ..region.region import Region
from . import common
from .region import import_data
from .. import climate_variables, corrections, downscalers



HELP = """Tools to downscale data"""

app = Typer(help=HELP, no_args_is_help=True)

NAME = 'Downscale'


@app.command()
def extra_tem_files(
    context: Context,
    destination: common.DESTINATION_DIR,
    overwrite: common.OVERWRITE_FLAG = False,

    ):
    """
    Function to prepare extra files for TEM, e.g.: vegetation, etc
    """
    log = context.obj.log

    log.info('Preparing TEM vegetation data...')
    veg = datasources.dataset.TEMDataset.from_vegetation(
        land_cover_raster=datasources.vegetation.land_cover_path, 
        land_cover_classes=datasources.vegetation.land_cover_classification, 
        global_political_map=datasources.vegetation.political_shp_path, 
        eco_region_map=datasources.vegetation.eco_shp_path, 
        region=context.obj.region
        )

    log.info('Importing vegetation data to region object...')    
    context.obj.region.import_datasource('vegetation', veg)

    log.info("Exporting the region object's vegetation data...")
    if context.obj.region:
        context.obj.callback_export_region(
            ['vegetation'], 
            overwrite=overwrite
    )

    log.info("Preparing TEM soil texture data....")
    soil_texture = datasources.dataset.TEMDataset.from_soil_texture('working/00-download/soiltexture', context.obj.region, logger=context.obj.log)

    log.info('Importing soil texture data to region object...')
    context.obj.region.import_datasource('soiltex', soil_texture)
    log.info("Exporting the region object's soil texture data...")
    if context.obj.region:
        context.obj.callback_export_region(
            ['soiltex'], 
            overwrite=overwrite
    )


@app.command()
def delta_method(
        context: Context,
        destination: common.DESTINATION_DIR,
        to_downscale: Annotated[Path, Argument(help="Path of data to be downscaled. This should be a directory containing netcdf files for each year of data you wish to downscale. See note if --use-region flag is provided.")],
        reference: Annotated[Path, Argument(help="Path to data to use as downscaling reference. This should be a single netcdf file with long term climate normals. See note if --use-region flag is provided. ")],
        variables: Annotated[List[str], Argument(help="list of variables to downscale")] = None,
        baseline: Annotated[Path, Option(help="Path to optional precalculated baseline data to use. A single netcdf file. See note if --use-region flag is provided.")]=None,
        baseline_years: Annotated[tuple[int, int], Option(help="Start and end of years (inclusive) to calculate climate baseline for if not provided")] = None,
        baseline_name: Annotated[str, Option(help=f"Name to save baseline data as. Data is saved as baseline_name.nc in destinations directory when no region is provided, otherwise it's saved in the region.  When not provided -baseline is appended to source")] = None,
        save_baseline: Annotated[str, Option(help="Flag to save baseline data when it has to be calculated")] = False,
        correction_factors: Annotated[str, Option(help="Path to optional precalculated correction factor data to use, See note if --use-region flag is provided.")] = None,
        save_correction_factors: Annotated[str, Option(help="Flag to save correction factor data when it has to be calculated")] = False,
        downscale_years: Annotated[tuple[int, int], Option(help="Start and end of years to download data for. Will default to full range available if not provided")] = None,
    ):
    """This command downscale data via the delta-method

    Note: 
        If --use-region is provided, paths are treated as keys to imported data 
        from region.
    """
    log = context.obj.log
    overwrite = context.obj.overwrite
    cleanup = context.obj.cleanup
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

    if context.obj.region: 
        log.info('Using region from context')
        area = context.obj.region
        region_directory = context.obj.region_directory

        log.info('--use-region was provided so "to_downscale", "reference", and "baseline" will be treated as items in Region.data')
        to_downscale = str(to_downscale)
        reference = str(reference)
        baseline = str(baseline) if baseline else None
        destination = str(destination)

        for key in [to_downscale, reference, baseline]:
            if not key in area.data:
                if key is None:
                    continue
                log.error(f"You are using a region and to_downscale value of {key} not loaded, load with --load-data={key}")
                sys.exit(0)
    else:
        to_downscale_pth = Path(to_downscale)
        log.info(f'Using to_downscale data at: {to_downscale_pth}')
        if not to_downscale_pth.exists():
            log.error('Target to_downscale data does not exist...')
            sys.exit()

        reference_pth = Path(reference)
        log.info(f'Using reference data at: {reference_pth}')
        if not reference_pth.exists():
            log.error('Target reference data does not exist...')
            sys.exit()
            
        log.suspend()
        to_downscale_ds = datasources.timeseries.YearlyTimeSeries(to_downscale_pth, logger=log)
        reference_ds = datasources.dataset.TEMDataset(reference_pth, logger=log)

        log.resume()
        log.debug(f'Creating temp Region')

        area = Region.from_TEMDataset(to_downscale_ds.data[0], logger=log)
        to_downscale = to_downscale_pth.stem
        log.suspend()
        area.import_datasource(to_downscale, to_downscale_ds)
        log.resume()

        reference = reference_pth.stem
        area.import_datasource(reference, reference_ds)

        log.info('Setup complete!')

    if not baseline:
        log.info("Baseline data was not provided, Calculating......")
        if not baseline_name:
            baseline_name = to_downscale+"-baseline"
        area.calculate_climate_baseline(baseline_years[0], baseline_years[1], baseline_name, to_downscale)

        if save_baseline:
            log.info('... with --save-baseline. Saving Calculated baseline data.')
            if context.obj.region:
                context.obj.callback_export_region([baseline_name], overwrite=overwrite) #TODO would we want to overwrite here
            else:
                out_path = destination/f"{baseline_name}.nc"
                area.data[baseline_name].save(out_path, overwrite=overwrite)

    elif not context.obj.region:
        log.info("Baseline data was provided, Loading......")
        if not baseline_name:
            baseline_name = to_downscale+"-baseline"
        area.import_datasource(baseline_name, baseline)

    if baseline_name:
        baseline = baseline_name


    if not variables:
        variables = [v for v in area.data[to_downscale].data[0].dataset.data_vars if v in climate_variables.DOWNSCALE_SAFE]
    
    log.info(f'Downscaling {variables}')
    # sys.exit()

    if not correction_factors:
        correction_factors = to_downscale + '-correction-factors'

    variables = {var:{'function': var} for var in variables}

    area.calculate_correction_factors(baseline, reference, variables, factor_id=correction_factors)

    if save_correction_factors:
        log.info('... with --save-correction-factors. Saving Calculated correction factors.')
        if context.obj.region:
            context.obj.callback_export_region(
                [correction_factors], 
                overwrite=overwrite
            ) #TODO would we want to overwrite here
        else:
            out_path = destination/f"{correction_factors}.nc"
            area.data[correction_factors].save(
                out_path, overwrite=overwrite
            )

    if type(destination) is str:
        destination_name = destination
    else:
        destination_name =  to_downscale + '-downscaled'

    # variables = '...'
    log.info('Downscaling...')
    with parallel_config(backend="loky", n_jobs=n_process, verbose=1):
        area.delta_downscale_timeseries(
            destination_name, to_downscale, correction_factors, variables, parallel, years=downscale_years
        )

    log.info('Saving Results...')
    if context.obj.region:
        context.obj.callback_export_region(
            [destination_name], 
            overwrite=overwrite
        ) 
    else:
        out_path = destination
        area.data[destination_name].save(out_path, overwrite=overwrite)

    return area
