"""
CLI tools for exporting data to a model specific format.
---------------------------------------------------------

TODO:
  Everything.
"""

import pathlib

from typer import Typer, Argument, Option, Context #, Option
from typing import Annotated

import temds.cli.common
import temds.constants




HELP = """Tools to export data to a model specific format."""

app = Typer(help=HELP, no_args_is_help=True, invoke_without_command=True)

NAME = 'Export'

@app.callback()
def export_model(
        context: Context,
        destination: temds.cli.common.DESTINATION_DIR,
        format: Annotated[str, Option(help="Model format to export to.")] = None,
        which: Annotated[str, Option(help="Which dataset to export.")] = 'all',
        from_directory: Annotated[pathlib.Path, Option(help="Directory to read data from. Will default to region directory if --use-region is provided")] = None,

    ):
    """This command exports data to a model specific format"""
    log = context.obj.log
    overwrite = context.obj.overwrite
    # cleanup = context.obj.cleanup
    # parallel = context.obj.parallel
    # n_process = context.obj.get_n_process()
    # use_region = context.obj.use_region

    # THis ends up being slow to check because the context is loaded first
    # which requires loading the region data. Unless you use the --no-load-all flag.
    assert format == 'TEM', "Only TEM format is currently supported. Please specify --format TEM or implement a new format (see src/temds/cli/export.py)."

    log.info(f"Exporting data to TEM format. Destination: {destination}, Which dataset(s): {which}, From directory: {from_directory}")

    r = context.obj.region
    if r is None:
        log.error("No region provided. Please provide a region with the --use-region flag to export data.")
        return

    if which == 'all':
        log.info("Exporting all datasets...")
        dataset_list = temds.constants.TEMDS_DATASET_NAMES
    else:
        raise NotImplementedError("Only exporting all datasets is currently supported. Please specify --which all or implement a new option (see src/temds/cli/export.py).")
    
    for dataset_name in dataset_list:
        ret_code = r.export_TEM(dataset_name=dataset_name, where=destination)
        if ret_code:
            log.error(f"Failed to export dataset: {dataset_name}")




# Testing commands:

# Exporting....
# TEMdownscale \
#     --use-region working/02-qdm-temrs-site2a/ \
#     export --format TEM \
#     working/

# Ran into problem with veg not existing. So had to run this:
# TEMdownscale \
#   --overwrite 
#   --use-region working/02-qdm-temrs-site2a \
#   --no-load-all \
#   downscale extra-tem-files working/02-qdm-temrs-site2a/