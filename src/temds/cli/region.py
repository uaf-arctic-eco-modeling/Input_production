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
from typing import Annotated

import geopandas as gpd
from osgeo import gdal
import joblib


# from .. import datasources
from . import common
from . import mask
from ..region.region import Region
from ..region.subregion import SubregionGenerator, TileSizeTooBigError
from ..region.region import MaskBoundaryCompatibilityError
from ..region.tools import align_to_resolution, mask_boundary_compatibility_report
from ..region.mask import Mask
from ..datasources import dataset, timeseries


HELP = """Tools for region management"""

app = Typer(help=HELP, no_args_is_help=True)
app.add_typer(mask.app, name='mask')

NAME = 'Region'

@app.command()
def create(
        context: Context,
        destination: common.DESTINATION_DIR,
        boundary: Annotated[Path, Argument(help=f"Vector file with boundary defined")],
        mask: Annotated[Path, Option(help=f"Raster file defining mask of data. Mask is calculated and all values are set to True if not provided")] = None,
        # mask_exceeds_boundary: Annotated[bool, Option(help="Flag to indicate the provided mask raster exceeds the boundary, and should be clipped before creating region.")] = False,
        layer: Annotated[str, Option(help=f"Layer to select as boundary. Accepts an integer index or a string name matching the 'layer' column.")] = None, 
        resolution: Annotated[float, Option(help="Resolution, required if mast is not provided")] = None,
        crs: Annotated[str, Option(help="WKT formatted CRS")] = None,
        align: Annotated[bool, Option(help="Flag to force region to be aligned to resolution. It is a good idea to keep this true!")] = True
    ):
    """Preprocesses downloaded ERA5 daily data. Preprocessed data will be
    formatted to be read as a YearlyDataset.
    """
    log = context.obj.log
    log.info('Starting region create')

    boundary_gpd = gpd.read_file(boundary)
    if crs:
        boundary_gpd = boundary_gpd.to_crs(crs)

    if layer:
        try:
            layer_idx = int(layer)
            boundary_gpd = boundary_gpd.iloc[[layer_idx]].reset_index()
            log.info(f"Using layer index {layer_idx} for boundary")
        except ValueError:
            log.info(f"Using layer name '{layer}' for boundary")
            matches = boundary_gpd[boundary_gpd['layer'] == layer]
            if matches.empty:
                log.error(f"No features found with layer name '{layer}'")
                return
            boundary_gpd = matches.iloc[[0]].reset_index()
    else:
        boundary_gpd = boundary_gpd.iloc[[0]].reset_index()

  
    if mask:

        mask = Mask(gdal.Open(mask))

    elif not mask and resolution:
        log.info(f"Creating mask from boundary with resolution {resolution}")
        mask = Mask.from_extent(boundary_gpd, resolution, align_extent_to_resolution=align)
    else: # no mask, but resolution
        log.error("If you do not provide a mask(--mask) file you must provide a resolution (--resolution)")
        return
   
    if align:
        boundary_gpd = align_to_resolution(boundary_gpd, abs(mask.resolution[0]))

    try:
        new = Region(boundary_gpd, mask)
    except MaskBoundaryCompatibilityError:
        report = mask_boundary_compatibility_report(mask, boundary_gpd)
        print(report)
        log.error(f"The boundary, and provided mask are not compatible.")
        if not report[0]:
            log.error('... The CRSs are not the same.')
        if not report[1]:
            log.error('... The boundary and masks shape are do not match.')
        if not report[2]:
            log.error('... The boundary and masks geotransform do not match.')
        return


    context.obj.region = new
    context.obj.region_directory = destination
    context.obj.callback_export_region()
    # new.export_to_directory(destination)

    log.info('Create region Complete!')

@app.command()
def divide(
    context: Context,
    destination: common.DESTINATION_DIR,
    source: common.SOURCE_DIR,
    size_x: Annotated[int, Argument(help=f"Target number of pixels for x dimension if each subregion ")],
    size_y: Annotated[int, Argument(help=f"Target number of pixels for y dimension if each subregion. Will uses size_x if not provided.")] = None
    ):
    """This command subdivides a soruce region in to multiple smaller regions.
    """
    log = context.obj.log
    log.info("Region division starting.")
    try:
        init = Region.from_directory(source)
    except FileNotFoundError:
        log.error(f'Region definition manifiest.yml not found in {source}')
        return
    if size_y is None:
        size_y = size_x

    try:
        srg = SubregionGenerator(init, size_x, size_y)
    except TileSizeTooBigError:
        log.error(f'Cannot sub-divide region with selected x and y sizes')
        return

    for ix in srg.tile_index.index:
        hix,vix =  srg.tile_index.loc[ix,['H','V']].values
        log.info(f'Generating sub-region {hix},{vix}')

        try:
            subregion = srg.generate_tile(ix)
        except RuntimeError:
            log.info('.. skipping, likely due to 0 in a dimension')
            continue
        log.info(f'.. exporting to  {hix},{vix}')
        subregion.export_to_directory(destination/f'H{hix}-V{vix}/')

    log.info('Region division complete!')

@app.command()
def import_data(
    context: Context,
    region_directory: common.DESTINATION_DIR,
    source_path: Annotated[Path, Argument(help=f"Path to input data")],
    name: Annotated[str, Argument(help=f"Name to use for imported data")] = None,
    # overwrite: common.OVERWRITE_FLAG = False,
    ):
    """This command imports data for a region. 
    """
    log = context.obj.log
    overwrite = context.obj.overwrite
    cleanup = context.obj.cleanup
    parallel = context.obj.parallel
    n_process = context.obj.get_n_process()

    if name is None:
        name = source_path.stem 

    

    log.info(f'Starting region import data for {name}')

    if context.obj.region: 
        log.info('Using region from context')
        area = context.obj.region
        region_directory = context.obj.region_directory
    else:
        log.info('Using region from argument')
        area = Region.from_directory(region_directory)
        context.obj.region = area
        context.obj.region_directory = Path(region_directory)

    if overwrite == False:
        if (region_directory/f'{name}.nc').exists() or (region_directory/f'{name}').exists():
            context.obj.overwrite_disabled_exit()
            


    if source_path is None:
        source = context.obj.runtime_data['source']
    else:
        if source_path.is_file():
            source = dataset.TEMDataset(source_path)
            if 'year' in source.dataset.attrs:
                source = dataset.YearlyDataset.from_TEMDataset(
                    source, source.dataset.attrs['year']
                )
        elif source_path.is_dir():
            source = timeseries.YearlyTimeSeries(source_path)
        else:
            log.error(f'source path is invalid. Cannot load source data from: {source_path}')
            sys.exit(0)

        

    log.info(f'Importing data to region {area.name} as {name}')

    with joblib.parallel_config(backend="loky", n_jobs=n_process, verbose=1):
        area.import_datasource(name, source, parallel=parallel)

    ## this callback checks the save_enabled and overwrite flags and
    ## saves data if necessary 
    with joblib.parallel_config(backend="loky", n_jobs=n_process, verbose=1):
        context.obj.callback_export_region([name], parallel=parallel)
        
        # try:
        #     area.export_to_directory(region_directory, items=[name], update_manifest=True, overwrite=overwrite)
        # except FileExistsError:
        #     log.error('Output files exist. Cannot save unless --overwrite is passed.')
        #     return
    log.info('Import data complete!')
    return area
