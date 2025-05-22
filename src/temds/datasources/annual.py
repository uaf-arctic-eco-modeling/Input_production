"""
Annual
------

Base class Objects representing annual data
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


class AnnualTimeSeries(UserList):
    """
    Base class for annual time series data

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
            ADType =  kwargs['ADType'] 

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

    def get_by_extent(self, minx, maxx, miny, maxy, extent_crs, **kwargs ):
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
                minx, maxx, miny, maxy, extent_crs,
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
                c_tile = helper(item)
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
        # def helper(item):
        #     out_file = op.joinpath(name_pattern.format(year=item.year))
        #     item.save(out_file, **kwargs)
        #     # gc.collect()
            

        if parallel:
            Parallel()(
                delayed(item.save)(op.joinpath(name_pattern.format(year=item.year)), **kwargs) for item in self.data
            )
        else:
            for item in self.data:
                if self.verbose: print(f'{item} saving' )
                helper(item)
                # out_file = op.joinpath(name_pattern.format(year=item.year))
                # item.save(out_file, **kwargs)

    def range(self):
        """get year range

        Returns
        -------
        range
        """
        return range(self.data[0].year, self.data[-1].year+1)


class AnnualDaily(TEMDataSet):
    """Daily for a year, This class 
    assumes data for a single year in input file
    """
    def __init__ (self, year, in_data, verbose=False, _vars=[], **kwargs):
        """
        Parameters
        ----------
        year: int
            year represented by data
        in_data: path
            When given an existing file (.nc), the file is loaded via `load`.
            or
            When given an existing directory, raw data is loaded via 
            `load_from_raw`. Also provide **kwargs as needed to use as optional
            arguments in `load_from_raw`
        verbose: bool, default False
            see `verbose`
        _vars: list, default CRU_JRA_VARS
            see `vars`
        **kwargs: dict
            arguments passed to non-default parameters of `load_from_raw` 
            if `in_data` is a directory.
        
        Attributes
        ----------
        self.year: int 
            year of data being represented.
        self.dataset: xarray.dataset 
            Daily CRU JRA data for a year
        self.verbose: bool
            when true status messages are enabled
        self.vars: list
            list of climate variables to load, defaults all(CRU_JRA_VARS)

        Raises
        ------
        IOError
            When file/files to load is wrong format or do not exist

        """
        # Why are we setting the year here and not looking it up?
        self.year = year
        self.dataset = None ## xarray data 
        self.verbose = verbose 
        

        ## I want to combine these
        self.vars = _vars
        self.naming = {}

        ## GEOSPATIAL STUFF
        self.crs = None
        self.transform = None


        if type(in_data) is xr.Dataset:
            self.dataset=in_data
            if 'crs' in kwargs:
                self.crs = kwargs['crs']
        else:
            in_data = Path(in_data)
            if in_data.exists() and in_data.suffix == '.nc':
                if 'year_override_callback' in kwargs:
                    year = int(kwargs['year_override_callback'](in_data.name))
                self.load(in_data, year_override=year, **kwargs)
            elif in_data.exists() and in_data.is_dir(): 
                self.load_from_raw(in_data, **kwargs) ## only on some types
            else:
                raise IOError('No Inputs found')

    def __repr__(self):
        return(f"{type(self).__module__}.{type(self).__name__}: {self.year}")

    def __lt__(self, other):
        """less than for sort
        """
        if self.year is None or other.year is None:
            raise AnnualDailyYearUnknownError(
                "One of the AnnualDaily objcets"
                " in comparison is missing 'year' attribute"
            )
        return self.year < other.year

    def update_variable_names(self, new_scheme):
        """
        """
        update_map = {self.naming[var] for var in new_scheme}
        self.dataset.rename(update_map)

        self.naming.update(new_scheme)

    def load(self, in_path, **kwargs):
        """Load daily data from a single file. Assumes file contains 
        all required variables, correct extent and daily timestep
        """
        print('annual')
        
        lookup = lambda kw, ke, de: kw[ke] if ke in kw else de
        year_override = lookup(kwargs, 'year_override', None)
        force_aoi_to = lookup(kwargs, 'force_aoi_to', None)
        aoi_nodata = lookup(kwargs, 'aoi_nodata', np.nan)
        crs = lookup(kwargs, 'crs', 'EPSG:4326')
        chunks = lookup(kwargs, 'chunks', None)


        if self.verbose: 
            print(f"loading file '{in_path}' assuming correct timestemp and "
                  "region are set"
            )
        self.dataset = xr.open_dataset(in_path, engine="netcdf4")

        if self.verbose: print(f'...loading dataset {chunks=}')
        self.dataset = xr.open_dataset(
            in_path, engine="netcdf4", chunks=chunks
        )

        if not force_aoi_to is None:
            if self.verbose: print(f'force AOI to {force_aoi_to} AOI for all vars')
            aoi_idx = np.isnan(self.dataset[force_aoi_to].values)
            mask = aoi_idx.astype(float)
            mask[mask == 1] = np.nan
            self.dataset = self.dataset + mask

        try: 
            if self.year is None and year_override is None:
                self.year = int(self.dataset.attrs['data_year'])
            elif type(year_override) is int:
                self.year = year_override
        except KeyError:
            raise AnnualDailyYearUnknownError(
                f"Cannot load year from nc file {in_path}. "
                "Missing 'data_year' attribute"

            )
        x_dim = 'x'
        y_dim = 'y'
        if crs == 'EPSG:4326':
            x_dim = 'lat'
            y_dim ='lon'
        self.dataset = \
            self.dataset.rio.write_crs(crs, inplace=True).\
                 rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim, inplace=True).\
                 rio.write_coordinate_system(inplace=True) 

        self.dataset = \
            self.dataset.rio.write_crs(crs, inplace=True).\
                 rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim, inplace=True).\
                 rio.write_coordinate_system(inplace=True) 


        if self.verbose: print('dataset initialized')
