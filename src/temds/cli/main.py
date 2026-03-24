from typer import Typer

from . import download
from . import preprocess

HELP = """Main CLI entry point for TEMDS tools"""

app = Typer(help=HELP, no_args_is_help=True)
app.add_typer(download.app, name='download')
app.add_typer(preprocess.app, name='preprocess')


if __name__ == "__main__":
    app()
