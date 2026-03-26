from dataclasses import dataclass, field
from pathlib import Path

from ..logger import Logger, INFO

from typer import Typer, Argument, Option, Context
from typing_extensions import Annotated

from datetime import datetime

@dataclass
class GlobalConfiguration:
    """"""
    log_file: Path = None
    log_level: str = 'TODO'
    silent: bool = False
    log: Logger = field(init=False)

    def __post_init__(self):
        self.log = Logger(verbose_levels=INFO, write_to=self.log_file)
        if self.silent:
            self.log.suspend

def years_as_range_check(years, as_range, default_range):

    if years is None:
        years = default_range
        as_range=True

    if len(years) == 2 and as_range:
        years = range(years[0], years[1]+1)
    return years


def dest_dir_callback(p):
    p.mkdir(exist_ok=True, parents=True)
    return p

def dest_file_callback(p):
    p.parent.mkdir(exist_ok=True, parents=True)
    return p
    
DESTINATION_DIR = Annotated[
    Path, Argument(
        help="Directory to save output files in.",
        callback=dest_dir_callback
    ),
]

DESTINATION_FILE = Annotated[
    Path, Argument(
        help="Output file",
        callback=dest_file_callback
    ),
]

SOURCE_DIR = Annotated[
    Path, Argument(
        help="Directory to read input files from",
    ),
]

SOURCE_FILE = Annotated[
    Path, Argument(
        help="Input file",
    ),
]

# YEARS_LIST =  Annotated[list[int], Argument(help="Years to preprocess, if not provided utility will attempt to process from 1940-2025")],


OVERWRITE_FLAG=  Annotated[bool, Option(help="Flag to overwrite existing data")]
CLEANUP_FLAG = Annotated[bool, Option(help="Flag to cleanup downloads by removing them")]
    
YEAR_RANGE_FLAG = Annotated[bool, Option(help="Flag to use years as range. Only applied when exactly 2 years are provided.")]

ERA5_YEARS = Annotated[list[int], Argument(help="Years to process, if not provided utility will attempt to process from 1940-2025" ,min=1940, max=datetime.now().year)]