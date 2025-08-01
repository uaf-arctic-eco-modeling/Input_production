"""
Downscaler functions
--------------------

original bash script code is in each docstring

# apply correction factors per month
# monthly correction factors convert to daily by setting each day to the monthly values
# per line 124-136 of downscaling.sh. In python we can do this directly on 
# data by adding a 2d array (monthly correction factor) to a 3d array
# (daily non downscaled data for each month) 

## i.e in 2d:[1,2,3] = [0,1,2] + 1
"""
import xarray as xr
import numpy as np

from .constants import ZERO_C_IN_K, SECONDS_PER_DAY, get_month_slice

def generic_delta_mul(not_downscaled, correction_factors, keys):
    """Generic delta downscaler should work if 
    units for data being downscaled and correction factors
    are the same (multiplication)
    """
    tods = keys['to_downscale']
    cfk = keys['correction_factor']

    downscaled_array = []
    # apply correction factors per month
    for mn_ix in range(12): # 0 based
        mn_slice = get_month_slice(mn_ix)

        monthly = not_downscaled[tods][mn_slice] * correction_factors[cfk][mn_ix]
        downscaled_array.append( monthly ) 

    downscaled = xr.concat(downscaled_array, dim='time')

    ## cleanup metadata here?

    return downscaled


def generic_delta_add(not_downscaled, correction_factors, keys):
    """Generic delta downscaler should work if 
    units for data being downscaled and correction factors
    are the same (multiplication)
    """
    tods = keys['to_downscale']
    cfk = keys['correction_factor']

    downscaled_array = []
    # apply correction factors per month
    for mn_ix in range(12): # 0 based
        mn_slice = get_month_slice(mn_ix)

        monthly = not_downscaled[tods][mn_slice] + correction_factors[cfk][mn_ix]
        downscaled_array.append( monthly ) 

    downscaled = xr.concat(downscaled_array, dim='time')

    ## cleanup metadata here?

    return downscaled

def wind_direction(not_downscaled, correction_factors, keys):
    """downscaling code for wind speed

    the code has moved so its just a pass through

    Returns
    -------
    xr.Dataset:
        downscaled data
    """  
    winddir = keys['winddir']
    return not_downscaled[winddir]

    
LOOKUP = {
    'temperature': generic_delta_add,
    'precipitation': generic_delta_mul,
    'vapor-pressure': generic_delta_mul,
    'radiation': generic_delta_mul,
    'wind-speed': generic_delta_mul,
    'wind-direction': wind_direction,
} 

