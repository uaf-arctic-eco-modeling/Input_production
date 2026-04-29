"""
CLI tools for exporting data to a model specific format.
---------------------------------------------------------

TODO:
  Everything.
"""

from typer import Typer, Argument, Option, Context #, Option
from typing import Annotated

import temds.cli.common




HELP = """Tools to export data to a model specific format."""

app = Typer(help=HELP, no_args_is_help=True, invoke_without_command=True)

NAME = 'Export'

@app.callback()
def export_model(
        context: Context,
        destination: temds.cli.common.DESTINATION_DIR,
        format: Annotated[str, Option(help="Model format to export to.")] = None,
    ):
    """This command exports data to a model specific format"""
    log = context.obj.log
    # overwrite = context.obj.overwrite
    # cleanup = context.obj.cleanup
    # parallel = context.obj.parallel
    # n_process = context.obj.get_n_process()
    # use_region = context.obj.use_region

    # THis ends up being slow to check because the context is loaded first
    # which requires loading the region data. Unless you use the --no-load-all flag.
    assert format == 'TEM', "Only TEM format is currently supported. Please specify --format TEM or implement a new format (see src/temds/cli/export.py)."

    log.info("Exporting data...")

    r = context.obj.region
    print("Here?")
    if r is None:
        log.error("No region provided. Please provide a region with the --use-region flag to export data.")
        return
    
    

    r.export_TEM(dataset_name='co2', where=destination)



    from IPython import embed; embed()



# Testing commands:
# TEMdownscale \
#     --use-region working/02-qdm-temrs-site2a/ \
#     export --format TEM \
#     working/