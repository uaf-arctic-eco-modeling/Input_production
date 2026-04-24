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
def calculate_normals(
        context: Context,
        destination: common.DESTINATION_FILE,
        source: Annotated[str, Argument(help="name of data in region to calculate baseline for")],
        years: Annotated[tuple[int, int], Argument(help="Start and end of years to download data for. Will default to full range of experiment provided")] = None,
        name: Annotated[str, Argument(help=f"name to save baseline data in region to; When not provided -baseline is appended to source")] = None,

    ):
    """This command calculates the long term climate normals for a daily dataset.
    """
    log = context.obj.log
    overwrite = context.obj.overwrite
    cleanup = context.obj.cleanup
    log.info('Starting calculate normals.')
    if context.obj.region: 
        # log.info('Using region from context')
        area = context.obj.region
        region_directory = context.obj.region_directory
    else:
        source_pth = Path(source)
        log.info(f'Using source data at: {source_pth}')
        if not source_pth.exists():
            log.error('Target source data does not exist...')
            sys.exit()
        log.suspend()
        source_ds = datasources.timeseries.YearlyTimeSeries(source_pth, logger=log)
        log.resume()
        log.debug(f'Creating temp Region')
        area = Region.from_TEMDataset(source_ds.data[0], logger=log)
        source = source_pth.stem
        log.suspend()
        area.import_datasource(source, source_ds)
        log.resume()
        log.info('Setup complete!')

    if name is None:
        name = source + f'-normals-{years[0]}-{years[1]}'

    area.calculate_climate_baseline(years[0], years[1], name, source)

    if context.obj.save_enabled:
        try:
            if context.obj.region: 
                area.export_to_directory(region_directory, items=[name], update_manifest=True, overwrite=overwrite)
            else:
                area.export_dataset(destination, name, overwrite=overwrite)
        except FileExistsError:
            log.error('Output files exist. Cannot save unless --overwrite is passed.')
            sys.exit(0)
    log.info("Calculating normals complete.")
    return area
