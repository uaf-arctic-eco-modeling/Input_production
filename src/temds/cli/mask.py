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


# from .. import datasources
from . import common
from ..region.mask import Mask

HELP = """Tools for region management"""

app = Typer(help=HELP, no_args_is_help=True)

NAME = 'Mask'

@app.command()
def create(
        context: Context,
        destination: common.DESTINATION_FILE,
        boundary: Annotated[Path, Argument(help=f"Vector file with boundary defined")],
        resolution: Annotated[float, Argument(help="Resolution")],
        layer: Annotated[str, Option(help=f"0 based index to layer to select as boundary")] = 0, 
        crs: Annotated[str, Option(help="WKT formatted CRS")] = None,
        align: Annotated[bool, Option(help="Flag to force region to ba aligned to resolution. It is a good idea to keep this true")] = True,
        uniform: Annotated[bool, Option(help="Flag to set all mask values to 1")] = False

    ):
    """Preprocesses downloaded ERA5 daily data. Preprocessed data will be
    formatted to be read as a YearlyDataset.
    """
    log = context.obj.log

    boundary = gpd.read_file(boundary).iloc[[layer]].reset_index()
    if crs:
        boundary = boundary.to_crs(crs)

    mask = Mask.from_extent(boundary, resolution, align_extent_to_resolution=align, fill_uniform=uniform)

    destination.parent.mkdir(exist_ok=True, parents=True)
    mask.to_file(destination)

    log.info('Complete!')

@app.command()
def generate_geopolitical_mask(
        context: Context,
        destination: common.DESTINATION_FILE,
        boundary: Annotated[Path, Argument(help=f"Vector file with boundary defined")],
        resolution: Annotated[float, Argument(help="Resolution")],
        feature: Annotated[str, Option(help=f"Feature to select as boundary")] = None, 
        crs: Annotated[str, Option(help="WKT formatted CRS")] = None,
        align: Annotated[bool, Option(help="Flag to force region to ba aligned to resolution. It is a good idea to keep this true")] = True

    ):
    """Preprocesses downloaded ERA5 daily data. Preprocessed data will be
    formatted to be read as a YearlyDataset.
    """
    log = context.obj.log
    print('TODO: this should generate a mask from the georegion and political maps')
    log.info('Complete!')