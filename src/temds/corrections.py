"""
Correction Factor functions
---------------------------

original bash script code is in each docstring


# this file is based on line 105 in downscaling.sh
   ## Compute the corrections
    # computing CRU-JRA vapor pressure based on Murray, F. W. 1967. 
    # “On the Computation of Saturation Vapor Pressure.” J. Appl. Meteor. 6 (1): 203–4 ; 
    # Shaman, J., and M. Kohn. 2009. “Absolute Humidity Modulates Influenza Survival, 
    # Transmission, and Seasonality.” PNAS 106 (9): 3243–8)
"""

def generic_delta_add(baseline, reference):
    """Generic correction factor calculation for additive
    delta downscaling  

    Parameters
    ----------
    baseline: xr.DataArray
        Baseline climate calculated from data to be downscaled
    reference: xr.DataArray
        High resolution climate reference
    
    Returns
    -------
    xr.DataArray
        correction factors
    """
    return reference - baseline 

def generic_delta_mul(baseline, reference):
    """Generic correction factor calculation for multiplicative
    delta downscaling  

        Parameters
    ----------
    baseline: xr.DataArray
        Baseline climate calculated from data to be downscaled
    reference: xr.DataArray
        High resolution climate reference
    
    Returns
    -------
    xr.DataArray
        correction factors
    """
    return reference / baseline 



LOOKUP = {
    'temperature': generic_delta_add,
    'precipitation': generic_delta_mul,
    'vapor-pressure': generic_delta_mul,
    'radiation': generic_delta_mul,
    'wind-speed': generic_delta_mul,
    'tair_min': generic_delta_add,
    'tair_max': generic_delta_add,
    'tair_avg': generic_delta_add,
    'prec': generic_delta_mul,  
    'nirr': generic_delta_mul,
    'vapo': generic_delta_mul,
    'wind': generic_delta_mul,
} 
