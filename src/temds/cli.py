import typer
from typing_extensions import Annotated

from . import subprograms


app = typer.Typer()

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
    print(f"Downloading {what}")

if __name__ == "__main__":
    app()
