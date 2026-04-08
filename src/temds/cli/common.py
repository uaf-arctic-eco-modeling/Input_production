"""
Common CLI features and definitions
-----------------------------------

TODO:
    - Allow for different log levels. Appending to log_file?
"""
from datetime import datetime
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

from typer import Argument, Option

from ..logger import Logger, INFO
from ..region.region import Region

@dataclass
class GlobalConfiguration:
    """Defines storage for global CLI configuration options

    Attributes
    ----------
    log_file: Path
        Optional path to save final log file to
    log_level: 
        Reserved for future extension
    silent: bool
        Flag to disable printing log messages to console.
    logger: Logger
        Logger for cli application
    """
    log_file: Path = None
    log_level: str = 'TODO'
    silent: bool = False
    region_directory: Path = None
    log: Logger = field(init=False)
    region: Region = field(init=False)

    def __post_init__(self):
        """Used to set up `log` with users options
        """
        self.log = Logger(verbose_levels=INFO, write_to=self.log_file)
        if self.silent:
            self.log.suspend()

        if self.region_directory:
            self.region = self.region.Region.from_directory(
                self.region_directory, self.log
            )
        else:
            self.region = None

def years_as_range_check(years: list[int], as_range: bool, default_range: list[int]) -> list | range:
    """Core function set up years uniformly among commands. When years has
    2 values and as_range is true a range is returned.  
    
    Parameters
    ----------
    years: list | None
        list of years provided to cli, If none default_range is used.
    as_range: bool
        value of argument with YEAR_RANGE_FLAG type
    default_range: list[int]
        list with start_year and end_year values

    Returns
    -------
    list or range
    """
    if years is None:
        years = default_range
        as_range=True

    if len(years) == 2 and as_range:
        years = range(years[0], years[1]+1)
    return years


def dest_dir_callback(p):
    """Callback to create missing directories from a path ending in a
    directory

    Parameters
    ----------
    p: Path

    Returns
    -------
    Path
    """
    p.mkdir(exist_ok=True, parents=True)
    return p

def dest_file_callback(p):
    """Callback to create missing directories from a path ending in a file name

    Parameters
    ----------
    p: Path

    Returns
    -------
    Path
    """
    p.parent.mkdir(exist_ok=True, parents=True)
    return p
    
## Uniform type for argument destination where destination is a directory
DESTINATION_DIR = Annotated[
    Path, Argument(
        help="Directory to save output files in.",
        callback=dest_dir_callback
    ),
]
    
## Uniform type for argument destination where destination is a file
DESTINATION_FILE = Annotated[
    Path, Argument(
        help="Output file",
        callback=dest_file_callback
    ),
]
## Uniform type for argument source directories
SOURCE_DIR = Annotated[
    Path, Argument(
        help="Directory to read input files from",
    ),
]

## Uniform type for argument source files
SOURCE_FILE = Annotated[
    Path, Argument(
        help="Input file",
    ),
]

## Uniform type for argument for years for ERA5 specific commands
ERA5_YEARS = Annotated[
    list[int], 
    Argument(
        help="Years to process, if not provided utility will attempt to process from 1940-2025",
        min=1940, max=datetime.now().year
    )
]

## Uniform type for option overwrite
OVERWRITE_FLAG=  Annotated[
    bool, 
    Option(help="Flag to overwrite existing data")
]

## Uniform type for option cleanup
CLEANUP_FLAG = Annotated[
    bool, 
    Option(help="Flag to cleanup downloads by removing them")
]
    
## Uniform type for option years_as_range
YEAR_RANGE_FLAG = Annotated[
    bool, 
    Option(
        help="Flag to use years as range. Only applied when exactly 2 years are provided."
    )
]

