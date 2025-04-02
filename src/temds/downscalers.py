
import xarray as xr

from .worldclim import MONTH_START_DAYS, DAYS_PER_MONTH



ZERO_C_IN_K = 273.15 # degrees kelvin
SECONDS_PER_DAY = 24 * 60 * 60

 # - 1 for zero based adjustment
get_month_slice = lambda mn: slice(MONTH_START_DAYS[mn]-1, DAYS_PER_MONTH[mn])



def temperature(not_downscaled, correction_factors, keys):
    """downscaling code for tmin, tmax, tavg

    Parameters
    ---------

    Returns
    -------
    """    
    tk = keys['temperature']
    cfk = keys['correction_factor']

    #convert c to k for entire year
    not_downscaled_k = not_downscaled[tk] - ZERO_C_IN_K  # K

    downscaled_array = []
    # apply correction factors per month
    for mn_ix in range(12): # 0 based
        mn_slice = get_month_slice(mn_ix)

        monthly = not_downscaled_k[mn_slice] + correction_factors[cfk][mn_ix]
        downscaled_array.append( monthly ) 

    downscaled = xr.concat(downscaled_array, dim='time')

    ## cleanup metadata here?

    return downscaled

def precipitation(not_downscaled, correction_factors, keys):
    """downscaling code 

    Parameters
    ---------

    Returns
    -------
    """    
    prk = keys['precipitation']
    cfk = keys['correction_factor']

    downscaled_array = []
    # apply correction factors per month
    for mn_ix in range(12): # 0 based
        mn_slice = get_month_slice(mn_ix)

        monthly = not_downscaled[prk][mn_slice] * correction_factors[cfk][mn_ix]
        downscaled_array.append( monthly ) 

    downscaled = xr.concat(downscaled_array, dim='time')

    ## cleanup metadata here?

    return downscaled

LOOKUP = {
    'temperature': temperature,
    'precipitation': precipitation
} 
