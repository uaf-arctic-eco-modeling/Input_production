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

import geopandas as gpd
from osgeo import gdal


# from .. import datasources
from . import common
from . import mask
from ..region.region import Region
from ..region.subregion import SubregionGenerator, TileSizeTooBigError
from ..region.region import MaskBoundaryCompatibilityError
from ..region.tools import align_to_resolution, mask_boundary_compatibility_report
from ..region.mask import Mask

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
        layer: Annotated[int, Option(help=f"layer to select as boundary")] = None, 
        resolution: Annotated[float, Option(help="Resolution, required if mast is not provided")] = None,
        crs: Annotated[str, Option(help="WKT formatted CRS")] = None,
        align: Annotated[bool, Option(help="Flag to force region to ba aligned to resolution. It is a good idea to keep this true")] = True

    ):
    """Preprocesses downloaded ERA5 daily data. Preprocessed data will be
    formatted to be read as a YearlyDataset.
    """
    log = context.obj.log


    boundary_gpd = gpd.read_file(boundary)
    if crs:
        boundary_gpd = boundary_gpd.to_crs(crs)

    if layer:
        boundary_gpd = boundary_gpd.loc[[layer]].reset_index()
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


    new.export_to_directory(destination)

    log.info('Complete!')

@app.command()
def divide(
    context: Context,
    destination: common.DESTINATION_DIR,
    source: common.SOURCE_DIR,
    size_x: Annotated[int, Argument(help=f"Target number of pixels for x dimension if each subregion ")],
    size_y: Annotated[int, Argument(help=f"Target number of pixels for y dimension if each subregion. Will uses size_x if not provided.")] = None
    ):
    log = context.obj.log
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





    log.info('Complete!')
