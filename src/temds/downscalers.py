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

from .constants import  get_month_slice

def generic_delta_mul(not_downscaled, correction_factors):
    """Generic delta downscaler should work if 
    units for data being downscaled and correction factors
    are the same (multiplication)
    """
    downscaled_array = []
    # apply correction factors per month
    for mn_ix in range(12): # 0 based
        mn_slice = get_month_slice(mn_ix)

        monthly = not_downscaled[mn_slice] * correction_factors[mn_ix]
        downscaled_array.append( monthly ) 

    downscaled = xr.concat(downscaled_array, dim='time')

    ## cleanup metadata here?

    return downscaled


def generic_delta_add(not_downscaled, correction_factors):
    """Generic delta downscaler should work if 
    units for data being downscaled and correction factors
    are the same (multiplication)
    """

    downscaled_array = []
    # apply correction factors per month
    for mn_ix in range(12): # 0 based
        mn_slice = get_month_slice(mn_ix)

        monthly = not_downscaled[mn_slice] + correction_factors[mn_ix]
        downscaled_array.append( monthly ) 

    downscaled = xr.concat(downscaled_array, dim='time')

    ## cleanup metadata here?

    return downscaled

def wind_direction(not_downscaled, correction_factors):
    """downscaling code for wind speed

    the code has moved so its just a pass through

    Returns
    -------
    xr.Dataset:
        downscaled data
    """  
    return not_downscaled

    
LOOKUP = {
    'temperature': generic_delta_add,
    'precipitation': generic_delta_mul,
    'vapor-pressure': generic_delta_mul,
    'radiation': generic_delta_mul,
    'wind-speed': generic_delta_mul,
    'wind-direction': wind_direction,
    'tair_min': generic_delta_add,
    'tair_max': generic_delta_add,
    'tair_avg': generic_delta_add,
    'prec': generic_delta_mul,  
    'nirr': generic_delta_mul,
    'vapo': generic_delta_mul,
    'wind': generic_delta_mul,
    'winddir': wind_direction,
} 

