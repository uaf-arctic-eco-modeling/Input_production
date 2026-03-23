from typer import Typer

from . import download

HELP = """Main CLI entry point for TEMDS tools"""

app = Typer(help=HELP, no_args_is_help=True)
app.add_typer(download.app, name='download')


if __name__ == "__main__":
    app()
