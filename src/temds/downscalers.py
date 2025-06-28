"""
Downscaler functions
--------------------

original bash script code is in each docstring

"""
import xarray as xr
import numpy as np

from .constants import ZERO_C_IN_K, SECONDS_PER_DAY, get_month_slice

def temperature(not_downscaled, correction_factors, keys):
    """downscaling code for tmin, tmax, tavg

    
    original nco bash code: float((tmp - 273.15) + tair_corr_oC)

    Parameters
    ----------
    not_downscaled: xr.Dataset
        climate data
    correction_factors: xr.Dataset
        correction factors
    keys: dict 
        lookup table for variables in `not_downscaled` and
        `correction_factors`

        must contain items for:
        'temperature': temperature variable name in `not_downscaled`
        'correction_factor': temperature correction factor in `correction_factors`



    Returns
    -------
    xr.Dataset:
        downscaled data
    """    
    tk = keys['temperature']
    cfk = keys['correction_factor']

    #convert c to k for entire year
    not_downscaled_k = not_downscaled[tk] - ZERO_C_IN_K  # K

    downscaled_array = []
    # apply correction factors per month
    # monthly correction factors convert to daily by setting each day to the monthly values
    # per line 124-136 of downscaling.sh. In python we can do this directly on 
    # data by adding a 2d array (monthly correction factor) to a 3d array
    # (daily non downscaled data for each month) 

    ## i.e in 2d:[1,2,3] = [0,1,2] + 1

    # for each month apply the monthly correction factor to each day of that month
    for mn_ix in range(12): # 0 based
        mn_slice = get_month_slice(mn_ix)

        monthly = not_downscaled_k[mn_slice] + correction_factors[cfk][mn_ix]
        downscaled_array.append( monthly ) 

    downscaled = xr.concat(downscaled_array, dim='time')

    ## cleanup metadata here?

    return downscaled

def precipitation(not_downscaled, correction_factors, keys):
    """downscaling code for precipitation

    original nco bash code: float(pre * prec_corr_mm)

    Parameters
    ----------
    not_downscaled: xr.Dataset
        climate data
    correction_factors: xr.Dataset
        correction factors
    keys: dict 
        lookup table for variables in `not_downscaled` and
        `correction_factors`

        must contain items for:
        'precipitation': precipitation variable name in `not_downscaled`
        'correction_factor': precipitation correction factor in `correction_factors`



    Returns
    -------
    xr.Dataset:
        downscaled data
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


def vapor_pressure (not_downscaled, correction_factors, keys):
    """downscaling code for vapor pressure

    original nco bash code: 
        vapo_Pa[$time,$lat,$lon] = float(((pres * spfh) / (0.622 + 0.378 * spfh)) * vapo_corr_Pa); 
    
    Parameters
    ----------
    not_downscaled: xr.Dataset
        climate data
    correction_factors: xr.Dataset
        correction factors
    keys: dict 
        lookup table for variables in `not_downscaled` and
        `correction_factors`

        must contain items for:
        'pres': pres variable name in `not_downscaled`
        'spfh': spfh variable name in `not_downscaled`
        'correction_factor': vapor pressure correction factor in `correction_factors`



    Returns
    -------
    xr.Dataset:
        downscaled data
    """  
    pres_key = keys['pres']
    spfh_key = keys['spfh']
    cfk = keys['correction_factor']

    pres = not_downscaled[pres_key]
    spfh = not_downscaled[spfh_key]


    downscaled_array = []
    for mn_ix in range(12): # 0 based
        mn_slice = get_month_slice(mn_ix)

        monthly = ( (pres[mn_slice] * spfh[mn_slice]) / (0.622 + 0.378 * spfh[mn_slice]) ) * correction_factors[cfk][mn_ix]
        downscaled_array.append( monthly ) 

    downscaled = xr.concat(downscaled_array, dim='time')
    


    return downscaled
    



def radiation (not_downscaled, correction_factors, keys):
    """downscaling code for vapor radiation 

    original nco bash code: 
        nirr_Wm2[$time,$lat,$lon] = float((dswrf / (6 * 60 * 60)) * nirr_corr_W_m2);

    Parameters
    ----------
    not_downscaled: xr.Dataset
        climate data
    correction_factors: xr.Dataset
        correction factors
    keys: dict 
        lookup table for variables in `not_downscaled` and
        `correction_factors`

        must contain items for:
        'dswf': downward short wave radiation variable name in `not_downscaled`
        'correction_factor': dswf factor in `correction_factors`



    Returns
    -------
    xr.Dataset:
        downscaled data
    """  
    dswrf = keys['dswrf']
    cfk = keys['correction_factor']



    downscaled_array = []
    for mn_ix in range(12): # 0 based
        mn_slice = get_month_slice(mn_ix)

        monthly = (not_downscaled[dswrf][mn_slice] / (6 * 60 * 60) ) * correction_factors[cfk][mn_ix]
        downscaled_array.append( monthly ) 

    downscaled = xr.concat(downscaled_array, dim='time')
    


    return downscaled



def wind_speed (not_downscaled, correction_factors, keys):
    """downscaling code for wind speed

    original nco bash code: 
        wind_ms[$time,$lat,$lon] = float(sqrt(ugrd^2 + vgrd^2) * ws_corr_ms)' 

    Parameters
    ----------
    not_downscaled: xr.Dataset
        climate data
    correction_factors: xr.Dataset
        correction factors
    keys: dict 
        lookup table for variables in `not_downscaled` and
        `correction_factors`

        must contain items for:
        'ugrd': ugrd variable name in `not_downscaled`
        'vgrd': vgrd variable name in `not_downscaled`
        'correction_factor': wind speed correction factor in `correction_factors`



    Returns
    -------
    xr.Dataset:
        downscaled data 
    """  

    ugrd = keys['ugrd']
    vgrd = keys['vgrd']
    cfk = keys['correction_factor']



    downscaled_array = []
    for mn_ix in range(12): # 0 based
        mn_slice = get_month_slice(mn_ix)

        # this is solving the pythagorean theorem  for 'c' = wind speed
        # a^2 + b^2 part  a == ugrd, b == vgrd
        a2_p_b2 = (not_downscaled[ ugrd ][mn_slice]**2) + (not_downscaled[ vgrd ][mn_slice]**2)
        ## sqrt(a2_p_b2) * cf
        monthly = np.sqrt(a2_p_b2) * correction_factors[cfk][mn_ix]
        downscaled_array.append( monthly ) 

    downscaled = xr.concat(downscaled_array, dim='time')
    


    return downscaled


   
def wind_direction(not_downscaled, correction_factors, keys):
    """downscaling code for wind speed

    original nco bash code: 
        winddir_deg[$time,$lat,$lon] = float((360/2)*(1+(ugrd/abs(ugrd)))+(180/3.14159265358979323844)*atan2(ugrd,vgrd));

    Parameters
    ----------
    not_downscaled: xr.Dataset
        climate data
    correction_factors: xr.Dataset
        correction factors
    keys: dict 
        lookup table for variables in `not_downscaled` and
        `correction_factors`

        must contain items for:
        'ugrd': ugrd variable name in `not_downscaled`
        'vgrd': vgrd variable name in `not_downscaled`



    Returns
    -------
    xr.Dataset:
        downscaled data
    """  
    ugrd_key = keys['ugrd']
    vgrd_key = keys['vgrd']
    # cfk = keys['correction_factor']





    downscaled_array = []
    # dont need loop?
    for mn_ix in range(12): # 0 based
        mn_slice = get_month_slice(mn_ix)
        ugrd = not_downscaled[ ugrd_key ][mn_slice]
        vgrd = not_downscaled[ vgrd_key ][mn_slice]
        
        monthly = ((360.0/2.0) * (1 + (ugrd/np.abs(ugrd)))) \
                + ((180.0/np.pi)*np.atan2(ugrd,vgrd))
        downscaled_array.append( monthly ) 

    downscaled = xr.concat(downscaled_array, dim='time')
    


    return downscaled



LOOKUP = {
    'temperature': temperature,
    'precipitation': precipitation,
    'vapor-pressure': vapor_pressure,
    'radiation': radiation,
    'wind-speed': wind_speed,
    'wind-direction': wind_direction,
} 
