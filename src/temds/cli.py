import typer
from typing_extensions import Annotated
from typing import Literal, List

from . import subprograms

VALID_SUBPROGRAMS = Literal['download', 'preprocess', 'setup']

app = typer.Typer()

@app.command()
def bucketfill_cru():
    print("need to implement this. Call all the bucket filling functions using "
          "CloudShellBucketFiller?")
    subprograms.bucketfill_cru()

@app.command()
def spatial_crop_cru():
    print("Need to call the spatial_crop_cru func...")
    subprograms.spatial_crop_cru()

@app.command()
def prepare_aoi():
    print("Should start from scratch, download some data for the aoi mask, and "
          "create the aoi based on the downloaded files. results in two shape "
          "files in your 'working' directory")

@app.command()
def prepare_tile_folders():
    print("Run this after you have an AOI. This cuts the AOI up into tiles and "
          "makes a folder for each tile. Inside each folder will be some shape "
          "files that define the tile extent. There should also be a tile "
          "index file that is a shape file with a polygon for each tile folder")
    



@app.command()
def setup(
        what: str,
        config: Annotated[str, typer.Argument(help="YAML configuration to use in lieu of command line arguments")]=None, 
        root: str = None, 
        # aoi:str=None, 
        # download:str=None, 
        # preprocessed:str=None, 
        # tiles:str=None, 
        # final:str=None
    ):
    print(root)
    if 'directories' == what:
        subprograms.setup_directories(
            config, #root , aoi, download, preprocessed, tiles, final
        )
    elif 'clean' == what:
        print('should clean up stuff') 

@app.command()
def download(
        what: Annotated[str, typer.Argument(help="Name of the dataset to download")], 
        config: Annotated[str, typer.Argument(help="YAML configuration to use in lieu of command line arguments")]=None, 
        save_to: Annotated[str, typer.Argument(help="Location where downloaded data is saved")]='default', 
        url_pattern: Annotated[str, typer.Argument(help="URL pattern for remote data ")]='default', 
        overwrite: Annotated[bool, typer.Argument(help="Flag to overwrite existing data")]=True, 
    ):

    subprograms.download(what, config, save_to, url_pattern, overwrite)

@app.command()
def preprocess(what: str, where: str = 'default'):
    print(f"Preprocessing {what}")
    ## IF data is missing download first
    ## currently download() does this
    # TODO

# @ app.command() ## want somthing like this but need to look into typer more
# def run(subprograms: List[VALID_SUBPROGRAMS], config: str):
#     if 'download' in list:
#         print('downloading')
#         # download('worldclim', config)

if __name__ == "__main__":
    app()
