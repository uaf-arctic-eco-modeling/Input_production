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



# # this needs to be implemented in dataset.py
# def load_from_raw(
#         self, data_path, aoi_extent=None, file_format = None, 
#         cleanup_uncompressed=True
#     ):
#     """Loads raw (direct from source) CRU JRA files, resamples to a daily
#     timestep, and clips to an extent if provided. The raw data is expected to 
#     be have been downloaded from CRU in the .gz compressed format.
#     The files are expected to have following format for names:
#         "{var}/crujra.v2.5.5d.{var}.{yr}.365d.noc.nc.gz"
#     where {var} is the variable name and {yr} is the year of data.
#     The raw data is expected to be in a directory structure where each
#     variable is in a subdirectory named after the variable name. Each CRU 
#     file is expected to have a time dimension with a calendar attribute of
#     '365_day' or 'noleap' and be at a 6 hour resolution.

#     Parameters
#     ----------
#     data_path: path
#         a directory containing raw cru jra files to be loaded by matching
#         file_format. 
#     aoi_extent: tuple, optional
#         clipping extent(minx, miny, maxx, maxy) geo-coordinates in 
#         degrees(WGS84) # is this really the order we want?
#     file_format: str, defaults None
#         string that contains {var} and {yr} formatters to match. When 
#         None is passed, '{var}/crujra.v2.5.5d.{var}.{yr}.365d.noc.nc.gz' 
#         pattern is used; this format matches CUR JRA file format conventions
#         where each variable is nested in a {var} subdirectory at the root 
#         `data_path`
#     cleanup_uncompressed: bool, default True
#         if true uncompressed raw data is deleted when loading is complete
#     """
#     if not self.in_memory:
#         raise TypeError('Feature requires in memory dataset')

#     if self.verbose: print(f"Loading from raw data at '{data_path}'")

#     if file_format is None:
#         file_format = '{var}/crujra.v2.5.5d.{var}.{yr}.365d.noc.nc.gz'


#     local_dataset = None
#     for var in self.vars:
#         _path = os.path.join(
#             data_path, 
#             file_format.format(var=var, yr=self.year)
#         )
#         if self.verbose: 
#             print(f"..loading raw data for '{var}' from '{_path}'")

#         cleanup = False
#         temp = local_dataset[var]
#         method = CRUJRA_RESAMPLE_LOOKUP[var]
#         temp = temp.assign_attrs( {'cell_methods':f'time:{method}'} )
#         local_dataset = local_dataset.assign({var:temp})
        
#     self.dataset = local_dataset
#     if self.verbose: 
#         print('..All raw data successfully loaded clipped and resampled.')
#         print('dataset initialized')
#         if _path[-3:] == '.gz':
#             with gzip.open(_path, 'rb') as f_in:
#                 with open(_path[:-3], 'wb') as f_out:
#                     shutil.copyfileobj(f_in, f_out)
#             _path = _path[:-3]
#             # this ensures cleanup only occurs on files we uncompress
#             # and not already uncompressed files the user may still need
#             if cleanup_uncompressed:
#                 cleanup = True

#         temp = xr.open_dataset(_path, engine="netcdf4")
#         if not isinstance(temp.time.values[0], cftime.DatetimeNoLeap) and \
#             not hasattr(temp.time, 'calendar'):
#             raise errors.InvalidCalendarError(
#                 f"Unknown calendar for file '{_path}'. No time variable "
#                 "has no calendar attribute, and the time values are not in "
#                 "a recognized format."
#             )

#         if aoi_extent is not None:
#             if self.verbose: print('..clipping to aoi')
#             mask_x =  ( temp.lon >= aoi_extent[0] ) \
#                     & ( temp.lon <= aoi_extent[1] )
#             mask_y =  ( temp.lat >= aoi_extent[2] ) \
#                     & ( temp.lat <= aoi_extent[3] )
#             temp = temp.where(mask_x & mask_y, drop=True)


#         method = CRUJRA_RESAMPLE_LOOKUP[var]
#         temp = CRUJRA_RESAMPLE_METHODS[method] (temp)
#                             # yr_data['tmax'].resample(time='1D').mean()
        
#         if local_dataset is None:
#             local_dataset = temp
#         else:
#             local_dataset = local_dataset.assign({var:temp[var]})

#         if cleanup:
#             os.remove(_path)  

#     ## this is to set the attribute at the right level in the dataset
#     for var in self.vars:
#         temp = local_dataset[var]
#         method = CRUJRA_RESAMPLE_LOOKUP[var]
#         temp = temp.assign_attrs( {'cell_methods':f'time:{method}'} )
#         local_dataset = local_dataset.assign({var:temp})
        
#     self.dataset = local_dataset
#     if self.verbose: 
#         print('..All raw data successfully loaded clipped and resampled.')
#         print('dataset initialized')
    