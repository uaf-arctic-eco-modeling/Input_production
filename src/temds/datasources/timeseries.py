"""
timeseries
----------

list operations for timeseries based data
"""
from collections import UserList
from pathlib import Path
from datetime import datetime

from joblib import Parallel, delayed

import xarray as xr
import rioxarray
import numpy as np

from .dataset import YearlyDataset
from . import errors
from temds.logger import Logger

try:
    import ctypes
    libc = ctypes.CDLL("libc.so.6") # clearing cache 
    malloc_trim = libc.malloc_trim
except:
    malloc_trim = lambda x: x ## do nothing 


from temds import climate_variables
from temds import constants
import gc
from copy import deepcopy


class YearlyTimeSeries(UserList):
    """
    Attributes
    ----------
    data: list
    start_year: int
    verbose: bool

    """

    def __init__(self, data, logger=Logger(), **kwargs):
        """
        parameters
        ----------
        data:
        verbose: bool
            verbosity flag
        kwargs:
            forwarded to AnnualDaily's kwargs 
        """
        self.logger = logger

        is_list_ds = isinstance(data, list) and isinstance(data[0], xr.Dataset)
        is_list_of_paths = isinstance(data, list) and isinstance(data[0], Path) 
        is_dir = isinstance(data, Path) and data.is_dir()
        if is_dir or is_list_of_paths: 

            if is_dir:
                self.logger.info(f'loading from directory: {data}')
                files = list(data.glob('*.nc'))
            else: # is list of paths
                self.logger.info('loading from provided files')
                files = data
            
            start = datetime.now()

            data = []
            for file in files:
                self.logger.info(f'loading file{file}')
                # print(f'loading file{file}')
                data.append(YearlyDataset(None, file, logger=self.logger, **kwargs))

             
            total = (datetime.now()-start).total_seconds()
            n_files = len(list(files))

            self.logger.info(f'Elapsed time: {total} seconds. Time per load {total/n_files} seconds')

        if is_list_ds:
            data = [YearlyDataset(None, item, logger=self.logger, **kwargs) for item in data]

        
        self.data = sorted(data)
        self.start_year = 0 ## start year not set
        
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
        errors.ContinuityError: 
            This error is raised on discontinuity if raise_exception is true 

        Returns
        -------
        bool
            False if data is discontinuous
        """
        last_year = self.data[-1].year
        continuous = True
        if not advanced:
            self.logger.info('Checking Continuity (basic)')
            n_items = len(self.data)
            expected = (last_year - self.start_year) + 1 
            if expected != n_items:
                continuous = False
                if raise_exception:
                    raise errors.ContinuityError(f'{type(self).__name__}: expected {expected} items, but has {n_items}')
                
        else:
            self.logger.info('Checking Continuity (advanced)')
            for yr in range(self.start_year, last_year+1):
                self.logger.info(f'-- Checking {yr}')
                d_yr = self[yr].year
                if d_yr != yr:
                    self.logger.info(f'---- testing for year {yr} but found {d_yr} off by {d_yr - yr}')
                    continuous = False
                    if raise_exception:
                        raise errors.ContinuityError(f'{type(self).__name__}: expected {yr} but found {d_yr} off by {d_yr - yr}')
                    # break
        msg = 'Data is continuous'
        if continuous:
            msg = 'Data not is continuous'
        self.logger.info(msg)

        return continuous

    def __repr__(self):
        """String representation of object"""
        return(f'{type(self).__module__}.{type(self).__name__}\n-'+'\n-'.join([str(i) for i in self.data]))

    def __setitem__(self, index, item):
        """Disables setitem"""
        raise errors.YearlyTimeSeriesError('__setitem__ is not supported in AnnualTimeseries')

    def insert(self, index, item):
        """Disables insert"""
        raise errors.YearlyTimeSeriesError('insert is not supported in AnnualTimeseries')
    
    def append(self, item):
        """Disables append"""
        raise errors.YearlyTimeSeriesError('append is not supported in AnnualTimeseries')
    
    def extend(self, other):
        """Disables extend"""
        raise errors.YearlyTimeSeriesError('extend is not supported in AnnualTimeseries')

    def __add__(self, other):
        """Disables add"""
        raise errors.YearlyTimeSeriesError('+ is not supported in AnnualTimeseries')
    def __radd__(self, other):
        """Disables add"""
        raise errors.YearlyTimeSeriesError('+ is not supported in AnnualTimeseries')
    def __iadd__(self, other):
        """Disables add"""
        raise errors.YearlyTimeSeriesError('+ is not supported in AnnualTimeseries')

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
        YearlyDataset or ATsType are in kwargs

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
            YearlyDataset: 
                class that inherits from AnnualDaily
            ATsType: 
                class that inherits from AnnualTimeseries
        """
        tiles = []

        # resolution = kwargs['resolution'] if 'resolution' in kwargs else None
        parallel =  kwargs['parallel'] if 'parallel' in kwargs else False
        # n_jobs =  kwargs['n_jobs'] if 'n_jobs' in kwargs else None

        # helper = lambda item: YearlyDataset(
        #     item.year, 
        #     # item.get_by_extent(
        #     #     minx, miny, maxx, maxy, extent_crs,
        #     #     **kwargs
        #     # )
        # )
        helper = lambda item: item.get_by_extent(
                        minx, miny, maxx, maxy, extent_crs,
                        **kwargs
                    )

        if parallel:
            print('parallel')
            tiles = Parallel()(
                delayed(helper)(item) for item in self.data
            )
        else:
            print('not parallel')
            for item in self.data:
                print(f'{item} clipping' )
                # c_tile = helper(item)
                 
                temp = item.get_by_extent(
                        minx, miny, maxx, maxy, extent_crs,
                        **kwargs
                    )
                # c_tile = YearlyDataset(
                #     item.year,
                #     temp,
                # )
                tiles.append(temp)

        return YearlyTimeSeries(tiles, logger=self.logger)

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
                self.logger.info(f'{item} saving' )
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
    
    def verify(self):
        """Runs verify on each timestep"""
        verified, reasons = True, []
        for year in self.range():
            # print(year)
            v, r = self[year].verify()
            verified = v and verified
            reasons += r
        return verified, reasons
             
    def create_climate_baseline(self, start_year, end_year, parallel=False):
        """Create baseline climate variables for dataset; uses
        the methods defined in CRUJRA_BASELINE_LOOKUP Based on original 
        downscaling.sh line 77-80. Here calculations are split up by var
        and the result is combined into a single dataset at the end.

        Algorithm: (pixel wise)
            (A) For each variable, daily data for each year in [start_year, 
        end_year] is averaged. 
            (B) For each month, the mean (or sum) of the daily average(from A)
        is calculated, giving the monthly baseline.
            (C) Monthly results are combined as time steps in yearly 
        dataset(xr.concat)
            (D) Each variables yearly dataset is combined into a single 
        dataset(xr.merge). This dataset is geo-referenced with crs from 
        first year of self.data.

        Parameters
        ----------
        start_year: int
            Inclusive start year for baseline
        end_year: int
            Inclusive end year for baseline

        Returns
        -------
        xr.dataset
            Geo-referenced dataset with monthly baseline aggregate for each 
            climate variable. Dimensions are x,y, time. Time dimensions has 
            12 times steps
        """

        
        var_list = []
        doy = [constants.MONTH_START_DAYS[mn] for mn in range(12)]

        var_dict = {}
        for var, method  in climate_variables.BASELINE_LOOKUP.items():
            self.logger.info(f'creating baseline for {var} with  {method}')
            ts = [self[yr].dataset[var].values for yr in range(start_year, end_year)]
            daily_avg = np.array(ts).mean(axis=0)
            temp = []
            for mn in range(12):
                mn_slice = slice(
                        constants.MONTH_START_DAYS[mn]-1, ## - 1 for 0 based
                        constants.DAYS_PER_MONTH[mn]
                    )
                
                mn_data = daily_avg[mn_slice]
                self.logger.debug(f'Monthly Shape: {mn_data.shape}') 
                mn_ag = None
                if 'mean' == method:
                    mn_ag = mn_data.mean(axis=0)
                elif 'sum' == method:
                    mn_ag = np.nansum(mn_data, axis=0)
                else:
                    raise ValueError(f" Unknown method '{method}' for variable '{var}'")
                temp.append(mn_ag)
            var_cf = np.array(temp)
            var_dict[var] = var_cf
        
        coords = {
            'time': doy, 
            'x': deepcopy(self[start_year].dataset.coords['x']), 
            'y': deepcopy(self[start_year].dataset.coords['y'])
        }

        clim_ref = xr.Dataset(
            {var: xr.DataArray(
                var_dict[var], dims=['time','y','x'], coords=coords
            ) for var in var_dict}
        )
        
        clim_ref.rio.write_crs(
            self[start_year].dataset.rio.crs.to_wkt(), 
            inplace=True
        )
        gc.collect()
        return clim_ref
