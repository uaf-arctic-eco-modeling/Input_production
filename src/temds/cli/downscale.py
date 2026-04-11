"""
CLI tools for downscaling
-------------------------

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

HELP = """Tools to downscale data"""

app = Typer(help=HELP, no_args_is_help=True)

NAME = 'Downscale'

@app.command()
def delta_method(
        context: Context,
        destination: common.DESTINATION_DIR,
        to_downscale: Annotated[str, Argument(help="")],
        reference: Annotated[str, Argument(help="")],
        years: Annotated[tuple[int, int], Argument(help="Start and end of years to download data for. Will default to full range of experiment provided")] = None,
        # name: Annotated[str, Argument(help=f"name to save baseline data in region to; When not provided -baseline is appended to source")] = None,
        baseline: Annotated[Path| str, Option(help="Optional precalculated baseline data to use")]=None
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

        area = Region.from_directory(region_directory, logger=log) ## add an error message if this fails

    ## if baseline is provided as argument load precalculated baseline, else calculate from to downscale data if years are provided

    ## calculate correction factors

    ## downscale/ multithreading etc

    return area
