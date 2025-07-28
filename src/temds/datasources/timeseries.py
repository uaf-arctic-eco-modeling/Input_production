"""
timeseries
----------

list operations for timeseries based data
"""
from collections import UserList
from pathlib import Path
from datetime import datetime
import gc

from joblib import Parallel, delayed

import xarray as xr
import rioxarray
import numpy as np

from .base import TEMDataSet
from .errors import AnnualDailyContinuityError, InvalidCalendarError
from .errors import AnnualDailyYearUnknownError, AnnualTimeSeriesError


try:
    import ctypes
    libc = ctypes.CDLL("libc.so.6") # clearing cache 
    malloc_trim = libc.malloc_trim
except:
    malloc_trim = lambda x: x ## do nothing 



class YearlyTimeSeries(UserList):
    """

    Attributes
    ----------
    data: list
    start_year: int
    verbose: bool

    """

    def __init__(self, data, verbose=False, **kwargs):
        """
        parameters
        ----------
        data:
        verbose: bool
            verbosity flag
        kwargs:
            forwarded to AnnualDaily's kwargs 
        """
        ADType = AnnualDaily
        if 'ADType' in kwargs:
            ADType = kwargs['ADType'] 


        is_list_ds = isinstance(data, list) and isinstance(data[0], xr.Dataset)
        is_list_of_paths = isinstance(data, list) and isinstance(data[0], Path) 
        is_dir = isinstance(data, Path) and data.is_dir()
        if is_dir or is_list_of_paths: 

            if is_dir:
                if verbose: print(f'loading from directory: {data}')
                files = list(data.glob('*.nc'))
            else: # is list of paths
                if verbose: print('loading from provided files')
                files = data
            
            start = datetime.now()

            data = []
            for file in files:
                if verbose: print(f'loading file{file}')
                # print(f'loading file{file}')
                data.append(ADType(None, file, verbose, **kwargs))

             
            total = (datetime.now()-start).total_seconds()
            n_files = len(list(files))

            if verbose:
                print(f'Elapsed time: {total} seconds. Time per load {total/n_files} seconds')

        if is_list_ds:
            data = [ADType(None, item, verbose, **kwargs) for item in data]

        
        self.data = sorted(data)
        self.start_year = 0 ## start year not set
        self.verbose = verbose
        if hasattr(self.data[0], 'year'):
            self.start_year = self.data[0].year
        elif  'data_year' in self.data[0].attrs:
            self.start_year = self.data[0].attrs['data_year']
        
        self.check_continuity(raise_exception=True)
        self.check_continuity(advanced=True,raise_exception=True)


    def check_continuity(self, advanced=False, raise_exception=False):
        """Checks annual continuity of `data`

        Parameters
        ----------
        advanced: bool, default False
            When True Check each year for continuity
            when False checks expected items matches items in data
        raise_exception: bool, default False
            when True Raise exceptions on discontinuity

        Raises
        ------
        AnnualDailyContinuityError: 
            This error is raised on discontinuity if raise_exception is true 

        Returns
        -------
        bool
            False if data is discontinuous
        """
        last_year = self.data[-1].year
        continuous = True
        if not advanced:
            if self.verbose: print('Checking Continuity (basic)')
            n_items = len(self.data)
            expected = (last_year - self.start_year) + 1 
            if expected != n_items:
                continuous = False
                if raise_exception:
                    raise AnnualDailyContinuityError(f'{type(self).__name__}: expected {expected} items, but has {n_items}')
                
        else:
            if self.verbose: print('Checking Continuity (advanced)')
            for yr in range(self.start_year, last_year+1):
                if self.verbose: print(f'-- Checking {yr}')
                d_yr = self[yr].year
                if d_yr != yr:
                    if self.verbose: print(f'---- testing for year {yr} but found {d_yr} off by {d_yr - yr}')
                    continuous = False
                    if raise_exception:
                        raise AnnualDailyContinuityError(f'{type(self).__name__}: expected {yr} but found {d_yr} off by {d_yr - yr}')
                    # break


        if self.verbose and continuous: print('Data is continuous')
        if self.verbose and not continuous: print('Data is not continuous')
        return continuous

    def __repr__(self):
        """String representation of object"""
        return(f'{type(self).__module__}.{type(self).__name__}\n-'+'\n-'.join([str(i) for i in self.data]))

    def __setitem__(self, index, item):
        """Disables setitem"""
        raise AnnualTimeSeriesError('__setitem__ is not supported in AnnualTimeseries')

    def insert(self, index, item):
        """Disables insert"""
        raise AnnualTimeSeriesError('insert is not supported in AnnualTimeseries')
    
    def append(self, item):
        """Disables append"""
        raise AnnualTimeSeriesError('append is not supported in AnnualTimeseries')
    
    def extend(self, other):
        """Disables extend"""
        raise AnnualTimeSeriesError('extend is not supported in AnnualTimeseries')

    def __add__(self, other):
        """Disables add"""
        raise AnnualTimeSeriesError('+ is not supported in AnnualTimeseries')
    def __radd__(self, other):
        """Disables add"""
        raise AnnualTimeSeriesError('+ is not supported in AnnualTimeseries')
    def __iadd__(self, other):
        """Disables add"""
        raise AnnualTimeSeriesError('+ is not supported in AnnualTimeseries')

    def __getitem__(self, index):
        """Overload __getitem__ to allow year based indexing
        """
        if type(index) is int:
            yr = index-self.start_year
        else: #slice
            start = index.start - self.start_year
            stop = index.stop - self.start_year if index.stop else None
            step = index.step if index.step else None
            yr = slice(start, stop, step)
        return super().__getitem__(yr)

    def get_by_extent(self, minx, miny, maxx, maxy, extent_crs, **kwargs ):
        """Get by extent. Can optionally promote to child classes if 
        ADType or ATsType are in kwargs

        Parameters
        ----------
        minx: number
        maxx: number
        miny: number
        maxy: number
            extent coords
        extent_crs:
            crs of extent coords
        kwargs:
            resolution: number
                pixel resolution to get
            ADType: 
                class that inherits from AnnualDaily
            ATsType: 
                class that inherits from AnnualTimeseries
        """
        tiles = []

        resolution = kwargs['resolution'] if 'resolution' in kwargs else None
        ADType =  kwargs['ADType'] if 'ADType' in kwargs else AnnualDaily
        ATsType =  kwargs['ATsType'] if 'ATsType' in kwargs else AnnualTimeSeries
        parallel =  kwargs['parallel'] if 'parallel' in kwargs else False
        n_jobs =  kwargs['n_jobs'] if 'n_jobs' in kwargs else None

        helper = lambda item: ADType(
            item.year, 
            item.get_by_extent(
                minx, miny, maxx, maxy, extent_crs,
                **kwargs
            )
        )

        if parallel:
            print('parallel')
            tiles = Parallel()(
                delayed(helper)(item) for item in self.data
            )
        else:
            print('not parallel')
            for item in self.data:
                # if self.verbose: 
                print(f'{item} clipping' )
                # c_tile = helper(item)
                 
                temp = item.get_by_extent(
                        minx, miny, maxx, maxy, extent_crs,
                        **kwargs
                    )
                c_tile = ADType(
                    item.year,
                    temp,
                )
                tiles.append(c_tile)

        return ATsType(tiles)

    def save(self, where, name_pattern, **kwargs):
        """Saves each item in data

        Parameters
        ----------
        where: Path
            directory to save each item in
        name_pattern: str
            filename pattern containing {year}'
        kwargs:
            forwarded to each AnnualDaily.saves kwargs
            see base.TEMDataSet for details
        """
        parallel = kwargs['parallel'] if 'parallel' in kwargs else False

        op = Path(where)
        op.mkdir(exist_ok=True, parents=True)
            

        if parallel:
            Parallel()(
                delayed(item.save)(op.joinpath(name_pattern.format(year=item.year)), **kwargs) for item in self.data
            )
        else:
            for item in self.data:
                if self.verbose: print(f'{item} saving' )
                # helper(item)
                out_file = op.joinpath(name_pattern.format(year=item.year))
                item.save(out_file, **kwargs)

    def range(self):
        """get year range

        Returns
        -------
        range
        """
        return range(self.data[0].year, self.data[-1].year+1)

    def synthesize_to_monthly(self, target_vars, new_names=None):
        """Converts target_vars to monthly data (12*N_years timesteps)

        Parameters
        ----------
        target_vars: dict
            vars to convert to monthly data, and the methods to use
            for conversion 'mean', or 'sum':
            i. e. {'nirr': 'mean', 'prec': 'sum'}
        new_names: dict
            Maps var names in new dataset
            i.e: {'nirr':'nirr', 'prec':'precip'}

        Returns
        -------
        xr.Dataset:
            With 12*n_years time steps. Where n_years is the length if
            `self.data`
        """
        monthly = []
        for year in self.range():
            monthly.append(self[year].synthesize_to_monthly(target_vars, new_names))

        return xr.concat(monthly, dim='time')
