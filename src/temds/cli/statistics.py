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
import sys

from .. import datasources
from ..region.region import Region
from . import common
from .region import import_data

HELP = """Tools to preprocess data"""

app = Typer(help=HELP, no_args_is_help=True)

NAME = 'statistics'

@app.command()
def calculate_climate_baseline(
        context: Context,
        region_directory: common.DESTINATION_DIR,
        source: Annotated[str, Argument(help="name of data in region to calculate baseline for")],
        years: Annotated[tuple[int, int], Argument(help="Start and end of years to download data for. Will default to full range of experiment provided")] = None,
        name: Annotated[str, Argument(help=f"name to save baseline data in region to; When not provided -baseline is appended to source")] = None,

    ):
    """Preprocesses downloaded ERA5 daily data. Preprocessed data will be
    formatted to be read as a YearlyDataset.
    """
    log = context.obj.log
    overwrite = context.obj.overwrite
    cleanup = context.obj.cleanup

    if context.obj.region: 
        log.info('Using region from context')
        area = context.obj.region
        region_directory = context.obj.region_directory
    else:
        log.info('Using region from argument')
        area = Region.from_directory(region_directory, logger=log)

    if name is None:
        name = source + '-baseline'

    area.calculate_climate_baseline(years[0], years[1], name, source)

    if context.obj.save_enabled:
        try:
            area.export_to_directory(region_directory, items=[name], update_manifest=True, overwrite=overwrite)
        except FileExistsError:
            log.error('Output files exist. Cannot save unless --overwrite is passed.')
            sys.exit(0)
    return area
