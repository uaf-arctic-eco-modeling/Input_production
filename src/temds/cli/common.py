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
import sys

from typer import Argument, Option

from ..logger import Logger, INFO, ERROR, WARN, DEBUG
from ..region.region import Region


OVERWRITE_DISABLED_MSG = 'Overwriting data disabled, and resulting data already exists. Use --overwrite flag to enable. Exiting...'

@dataclass
class GlobalConfiguration:
    """Defines storage for global CLI configuration options

    Attributes
    ----------
    log_file: Path, Defaults None
        Optional path to save final log file to. By default no file is 
        written.
    log_level: str
        Sting log level. Options are 'ERROR', 'WARN', 'INFO', 'DEBUG', or
        'NONE'
    silent: bool, defaults False
        Flag to disable printing log messages to console.
    overwrite: bool, defaults False
        Flag to indicate that overwriting of output files is allowed
    cleanup: bool, defaults False
        See each command for how this flag is used
    region_directory: path, defaults None
        Path to a directory containing data for a region, and a manifest.yml
        file. When provided, `region` is loaded, and commands should use the 
        regions extent, and output directory when saving results instead
        of their destination argument
    import_data: list, Optional
        List of data in a regions manifest to load on creation. If not provided
        all_items are loaded.
    save_enabled: bool, defaults True
        This flag enables saving of output/intermediate data. When set to
        False writing of data should be disabled, which is useful when commands
        are called as part of a chain and not from the user interface level.

    log: Logger
        Logger for cli application
    region: Region
        Region to use for cli commands
    runtime_data: dict
        This dict exists to store data to pass cli functions when not
        being called directly at the user interface level. 
    """
    log_file: Path = None
    log_level: str = 'INFO'
    silent: bool = False
    overwrite: bool = False
    cleanup: bool = False
    region_directory: Path = None
    import_data: list = None
    save_enabled: bool = True
    fail_on_warn: bool = False
    in_memory: bool = True
    parallel: bool=False
    n_process: int=4
    log: Logger = field(init=False)
    region: Region = field(init=False)
    runtime_data: dict = field(init=False)

    def __post_init__(self):
        """Used to set up `log` with users options
        """
        verbose_levels = {
            'ERROR': ERROR,
            'WARN': WARN,  
            'INFO': INFO,
            'DEBUG': DEBUG,
            'NONE': []
        }[self.log_level.upper()]

        self.log = Logger(verbose_levels=verbose_levels, write_to=self.log_file)
        if self.silent:
            self.log.suspend()

        if not self.overwrite:
            self.log.warn('WARNING overwriting data is disabled') 
            if self.fail_on_warn:
                self.log.info('Exit on warnings has been enabled, goodbye!')
                sys.exit(0)

        if self.region_directory:
            self.log.info(f'Using Region at {self.region_directory}')
            self.region = Region.from_directory(
                self.region_directory, self.import_data, self.log
            )
        else:
            self.log.info(f'No Region provided')
            self.region = None
        self.runtime_data = {}


    def overwrite_disabled_exit(self):
        """Exits the program at start up if overwrite is disabled"""
        self.log.error(OVERWRITE_DISABLED_MSG)
        sys.exit(0)

    def callback_export_region(self, items: list|str = 'all', **kwargs):
        """Callback to export the region if it's configured in the configuration

        Parameters
        ----------
        items: list or str, defaults 'all'
            If a string is provided it must be 'all'
            otherwise it should be a list of items in the region to save
        kwargs: 
            kwargs to pass to regions export function.

        Raises
        ------
        FileExistsError:
            if region exists and overwrite is false
        """
        if self.save_enabled:   
            self.log.info(f'Saving {items} to region at {self.region_directory}.')
            try:
                kwargs['update_manifest'] = True
                kwargs['items'] = items
                kwargs['overwrite']=self.overwrite
                
                self.region.export_to_directory(
                    self.region_directory, **kwargs
                )
            except FileExistsError:
                self.log.error('Output files exist. Cannot save unless --overwrite is passed.')
                sys.exit(0)
        else:
            self.log.debug('Save has been disabled')
        
    def get_n_process(self) -> int:
        """Checks `parallel` and `n_process` to detrmine the number
        of processes available. 

        Returns
        -------
        int
        """
        return self.n_process if self.parallel else 1


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

