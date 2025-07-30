"""
CRU JRA
-------

Data structures representing CRU JRA data
"""
from cf_units import Unit
from temds import climate_variables 
from temds.constants import SECONDS_PER_DAY

NAME = 'crujra'

CITATION = "todo: find this"

## REGISTER CLIMATE VARIABLES
climate_variables.register('tair_avg', NAME, 'tmp')
climate_variables.register('tair_min', NAME, 'tmin')
climate_variables.register('tair_max', NAME, 'tmax')
climate_variables.register('prec', NAME, 'pre')
climate_variables.register('nirr', NAME, 'dswrf')
climate_variables.register('ugrd', NAME, 'ugrd')
climate_variables.register('vgrd', NAME, 'vgrd')
climate_variables.register('spfh', NAME, 'spfh')
climate_variables.register('pres', NAME, 'pres')

## this var is not present in raw data and has to be
## calculated from spfh and pres
climate_variables.register('vapo', NAME, 'vapo')

climate_variables.register_source_unit('tair_avg', NAME, Unit('celsius'))
climate_variables.register_source_unit('tair_min', NAME, Unit('celsius'))
climate_variables.register_source_unit('tair_max', NAME, Unit('celsius'))
climate_variables.register_source_unit('nirr', NAME, Unit(f'{ 1/SECONDS_PER_DAY} kilogram-second^-3'))


CRUJRA_VARS = climate_variables.aliases_for(NAME)

CRUJRA_RESAMPLE_LOOKUP = {
    'tmin': 'mean',
    'tmax': 'mean',
    'tmp': 'mean',
    'pre': 'sum',  
    'dswrf': 'sum',
    'ugrd': 'mean',
    'vgrd': 'mean',
    'spfh': 'mean',
    'pres': 'mean',
    
}

CRUJRA_BASELINE_LOOKUP = {
    'tmin': 'mean',
    'tmax': 'mean',
    'tmp': 'mean',
    'pre': 'sum',  
    'dswrf': 'mean',
    'ugrd': 'mean',
    'vgrd': 'mean',
    'spfh': 'mean',
    'pres': 'mean',
    
}

CRUJRA_RESAMPLE_METHODS  = {
    'mean': lambda x: x.resample(time='1D').mean(),
    'sum':  lambda x: x.resample(time='1D').sum(skipna = False), ## TEST this (the skipna), this should fix summing integer issues
}


def calculate_vapo(pres, spfh):
    """
    
    """
    return (0.001 * pres * spfh) / (0.622 + 0.378 * spfh)

# class AnnualTimeSeries(annual.AnnualTimeSeries):
#     def __init__(self, data, verbose=True, **kwargs):
#         """
#         parameters
#         ----------

#         """
#         kwargs['ADType'] = AnnualDaily
#         super().__init__(data, verbose, **kwargs)

#     def get_by_extent(self, minx, miny, maxx, maxy, extent_crs , **kwargs):
#         """"""
#         kwargs['ADType'] = AnnualDaily
#         kwargs['ATsType'] = AnnualTimeSeries
#         return super().get_by_extent(
#             minx, miny, maxx, maxy, extent_crs, 
#             **kwargs
#         )

            
#     def create_climate_baseline(self, start_year, end_year, parallel=False):
#         """Create baseline climate variables for dataset; uses
#         the methods defined in CRUJRA_BASELINE_LOOKUP Based on original 
#         downscaling.sh line 77-80. Here calculations are split up by var
#         and the result is combined into a single dataset at the end.

#         Algorithm: (pixel wise)
#             (A) For each variable, daily data for each year in [start_year, 
#         end_year] is averaged. 
#             (B) For each month, the mean (or sum) of the daily average(from A)
#         is calculated, giving the monthly baseline.
#             (C) Monthly results are combined as time steps in yearly 
#         dataset(xr.concat)
#             (D) Each variables yearly dataset is combined into a single 
#         dataset(xr.merge). This dataset is geo-referenced with crs from 
#         first year of self.data.

#         Parameters
#         ----------
#         start_year: int
#             Inclusive start year for baseline
#         end_year: int
#             Inclusive end year for baseline

#         Returns
#         -------
#         xr.dataset
#             Geo-referenced dataset with monthly baseline aggregate for each 
#             climate variable. Dimensions are x,y, time. Time dimensions has 
#             12 times steps
#         """

        
#         var_list = []
#         doy = [constants.MONTH_START_DAYS[mn] for mn in range(12)]

#         var_dict = {}
#         for var, method  in CRUJRA_BASELINE_LOOKUP.items():
#             if self.verbose: print('creating baseline for', var, 'with', method)
#             ts = [self[yr].dataset[var].values for yr in range(start_year, end_year)]
#             daily_avg = np.array(ts).mean(axis=0)
#             temp = []
#             for mn in range(12):
#                 mn_slice = slice(
#                         constants.MONTH_START_DAYS[mn]-1, ## - 1 for 0 based
#                         constants.DAYS_PER_MONTH[mn]
#                     )
                
#                 mn_data = daily_avg[mn_slice]
#                 if self.verbose: print('Monthly Shape:',mn_data.shape) 
#                 mn_ag = None
#                 if 'mean' == method:
#                     mn_ag = mn_data.mean(axis=0)
#                 elif 'sum' == method:
#                     mn_ag = np.nansum(mn_data, axis=0)
#                 else:
#                     raise ValueError(f"[crujra.AnnualTimeSeries.create_climate_baseline] Unknown method '{method}' for variable '{var}'")
#                 temp.append(mn_ag)
#             var_cf = np.array(temp)
#             var_dict[var] = var_cf
        
#         coords = {
#             'time': doy, 
#             'x': deepcopy(self[start_year].dataset.coords['x']), 
#             'y': deepcopy(self[start_year].dataset.coords['y'])
#         }

#         clim_ref = xr.Dataset(
#             {var: xr.DataArray(
#                 var_dict[var], dims=['time','y','x'], coords=coords
#             ) for var in var_dict}
#         )
        
#         clim_ref.rio.write_crs(
#             self[start_year].dataset.rio.crs.to_wkt(), 
#             inplace=True
#         )
#         gc.collect()
#         return clim_ref

# ## ---- end of AnnualTimeSeries ----


# class AnnualDaily(annual.AnnualDaily):
#     """
#     AnnualDaily class for managing and processing daily CRU JRA climate data.
#     This class provides functionality to load, process, and save daily climate
#     data from CRU JRA datasets. It supports loading data from raw files or
#     preprocessed NetCDF files, resampling to daily timesteps, clipping to a
#     geographic extent, and saving the processed data.

#     Attributes
#     ----------
#     year : int
#         The year represented by the data.
#     in_path : str or Path or xarray.Dataset
#         Path to the input data. If a NetCDF file is provided, it is loaded via
#         `load`. If a directory is provided, raw data is loaded via
#         `load_from_raw`. If an xarray.Dataset is provided, it is directly
#         assigned.
#     verbose : bool, optional, default=False
#         Enables status messages when set to True.
#     _vars : list, optional, default=CRUJRA_VARS
#         List of climate variables to load. Defaults to all variables in
#         `CRUJRA_VARS`.
#     **kwargs : dict
#         Additional arguments passed to `load_from_raw` when `in_path` is a
#         directory.
#     year : int
#         The year of the data being represented.
#     dataset : xarray.Dataset
#         The loaded daily CRU JRA data for the specified year.
#     verbose : bool
#         Indicates whether status messages are enabled.
#     vars : list
#         List of climate variables to load.

#     Methods
#     -------
#     __repr__()
#         Returns a string representation of the AnnualDaily object.
#     __lt__(other)
#         Compares two AnnualDaily objects based on their year attribute.
#     load_from_raw(data_path, aoi_extent=None, file_format=None, cleanup_uncompressed=True)
#         Loads raw CRU JRA files (6 hour time resolution, gloabl resolution),
#         resamples to daily timesteps, and clips to an extent if provided.
#     load(in_path, year_override=None)
#         Loads daily data from a single NetCDF file.
#     save(out_file, missing_value=1.e+20, fill_value=1.e+20, overwrite=False)
#         Saves the dataset as a NetCDF file.
#     reproject(crs)
#         Reprojects the dataset to a specified coordinate reference system (CRS).
#     get_by_extent(minx, miny, maxx, maxy, extent_crs, resolution, alg=Resampling.bilinear)
#         Extracts a subset of the dataset based on a specified geographic extent
#         and resolution.

#     Exceptions
#     ----------
#     IOError
#         Raised when the input file or directory does not exist or is in the
#         wrong format.
#     AnnualDailyYearUnknownError
#         Raised when the year attribute is missing during certain operations.
#     InvalidCalendarError
#         Raised when the calendar type in the dataset is invalid.

#     """
#     def __init__ (self, year, in_path, verbose=False, _vars=CRUJRA_VARS,  **kwargs):
#         """
#         Parameters
#         ----------
#         year: int
#             year represented by data
#         in_path: path
#             When given an existing file (.nc), the file is loaded via `load`.
#             or
#             When given an existing directly, raw data is loaded via 
#             `load_from_raw`. Also provide **kwargs as needed to use as optional
#             arguments in `load_from_raw`
#         verbose: bool, default False
#             see `verbose`
#         _vars: list, default CRUJRA_VARS
#             see `vars`
#         **kwargs: dict
#             arguments passed to non-default parameters of `load_from_raw` 
#             if `in_path` is a directory.
        
#         Attributes
#         ----------
#         self.year: int 
#             year of data being represented.
#         self.dataset: xarray.dataset 
#             Daily CRU JRA data for a year
#         self.verbose: bool
#             when true status messages are enabled
#         self.vars: list
#             list of climate variables to load, defaults all(CRUJRA_VARS)

#         Raises
#         ------
#         IOError
#             When file/files to load is wrong format or do not exist

#         """
#         super().__init__(year, in_path, verbose, _vars,  **kwargs)
#         self.resolution=None

#     ## this needs to be implemented in dataset.py
#     # def load_from_raw(
#     #         self, data_path, aoi_extent=None, file_format = None, 
#     #         cleanup_uncompressed=True
#     #     ):
#     #     """Loads raw (direct from source) CRU JRA files, resamples to a daily
#     #     timestep, and clips to an extent if provided. The raw data is expected to 
#     #     be have been downloaded from CRU in the .gz compressed format.
#     #     The files are expected to have following format for names:
#     #         "{var}/crujra.v2.5.5d.{var}.{yr}.365d.noc.nc.gz"
#     #     where {var} is the variable name and {yr} is the year of data.
#     #     The raw data is expected to be in a directory structure where each
#     #     variable is in a subdirectory named after the variable name. Each CRU 
#     #     file is expected to have a time dimension with a calendar attribute of
#     #     '365_day' or 'noleap' and be at a 6 hour resolution.

#     #     Parameters
#     #     ----------
#     #     data_path: path
#     #         a directory containing raw cru jra files to be loaded by matching
#     #         file_format. 
#     #     aoi_extent: tuple, optional
#     #         clipping extent(minx, miny, maxx, maxy) geo-coordinates in 
#     #         degrees(WGS84) # is this really the order we want?
#     #     file_format: str, defaults None
#     #         string that contains {var} and {yr} formatters to match. When 
#     #         None is passed, '{var}/crujra.v2.5.5d.{var}.{yr}.365d.noc.nc.gz' 
#     #         pattern is used; this format matches CUR JRA file format conventions
#     #         where each variable is nested in a {var} subdirectory at the root 
#     #         `data_path`
#     #     cleanup_uncompressed: bool, default True
#     #         if true uncompressed raw data is deleted when loading is complete
#     #     """
#     #     if not self.in_memory:
#     #         raise TypeError('Feature requires in memory dataset')

#     #     if self.verbose: print(f"Loading from raw data at '{data_path}'")

#     #     if file_format is None:
#     #         file_format = '{var}/crujra.v2.5.5d.{var}.{yr}.365d.noc.nc.gz'


#     #     local_dataset = None
#     #     for var in self.vars:
#     #         _path = os.path.join(
#     #             data_path, 
#     #             file_format.format(var=var, yr=self.year)
#     #         )
#     #         if self.verbose: 
#     #             print(f"..loading raw data for '{var}' from '{_path}'")

#     #         cleanup = False
#     #         temp = local_dataset[var]
#     #         method = CRUJRA_RESAMPLE_LOOKUP[var]
#     #         temp = temp.assign_attrs( {'cell_methods':f'time:{method}'} )
#     #         local_dataset = local_dataset.assign({var:temp})
            
#     #     self.dataset = local_dataset
#     #     if self.verbose: 
#     #         print('..All raw data successfully loaded clipped and resampled.')
#     #         print('dataset initialized')
#     #         if _path[-3:] == '.gz':
#     #             with gzip.open(_path, 'rb') as f_in:
#     #                 with open(_path[:-3], 'wb') as f_out:
#     #                     shutil.copyfileobj(f_in, f_out)
#     #             _path = _path[:-3]
#     #             # this ensures cleanup only occurs on files we uncompress
#     #             # and not already uncompressed files the user may still need
#     #             if cleanup_uncompressed:
#     #                 cleanup = True

#     #         temp = xr.open_dataset(_path, engine="netcdf4")
#     #         if not isinstance(temp.time.values[0], cftime.DatetimeNoLeap) and \
#     #             not hasattr(temp.time, 'calendar'):
#     #             raise errors.InvalidCalendarError(
#     #                 f"Unknown calendar for file '{_path}'. No time variable "
#     #                 "has no calendar attribute, and the time values are not in "
#     #                 "a recognized format."
#     #             )

#     #         if aoi_extent is not None:
#     #             if self.verbose: print('..clipping to aoi')
#     #             mask_x =  ( temp.lon >= aoi_extent[0] ) \
#     #                     & ( temp.lon <= aoi_extent[1] )
#     #             mask_y =  ( temp.lat >= aoi_extent[2] ) \
#     #                     & ( temp.lat <= aoi_extent[3] )
#     #             temp = temp.where(mask_x & mask_y, drop=True)


#     #         method = CRUJRA_RESAMPLE_LOOKUP[var]
#     #         temp = CRUJRA_RESAMPLE_METHODS[method] (temp)
#     #                             # yr_data['tmax'].resample(time='1D').mean()
           
#     #         if local_dataset is None:
#     #             local_dataset = temp
#     #         else:
#     #             local_dataset = local_dataset.assign({var:temp[var]})

#     #         if cleanup:
#     #             os.remove(_path)  

#     #     ## this is to set the attribute at the right level in the dataset
#     #     for var in self.vars:
#     #         temp = local_dataset[var]
#     #         method = CRUJRA_RESAMPLE_LOOKUP[var]
#     #         temp = temp.assign_attrs( {'cell_methods':f'time:{method}'} )
#     #         local_dataset = local_dataset.assign({var:temp})
            
#     #     self.dataset = local_dataset
#     #     if self.verbose: 
#     #         print('..All raw data successfully loaded clipped and resampled.')
#     #         print('dataset initialized')
        