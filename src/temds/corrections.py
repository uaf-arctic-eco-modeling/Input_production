
# this file is based on line 105 in downscaling.sh
   ## Compute the corrections
    # computing CRU-JRA vapor pressure based on Murray, F. W. 1967. 
    # “On the Computation of Saturation Vapor Pressure.” J. Appl. Meteor. 6 (1): 203–4 ; 
    # Shaman, J., and M. Kohn. 2009. “Absolute Humidity Modulates Influenza Survival, 
    # Transmission, and Seasonality.” PNAS 106 (9): 3243–8)
import xarray as xr




from .downscalers import ZERO_C_IN_K, SECONDS_PER_DAY


def temperature(baseline, reference, keys):
    """correction factor calculation code for tmin, tmax, tavg

    Parameters
    ---------

    Returns
    -------
    """   
    rk = keys['reference']
    bk = keys['baseline']

    correction_factor = reference[rk] - (baseline[bk] - ZERO_C_IN_K)

    return correction_factor

def precipitation (baseline, reference, keys):
    """correction factor calculation code for

    Parameters
    ---------

    Returns
    -------
    """  
    rk = keys['reference']
    bk = keys['baseline']
    return reference[rk]/baseline[bk]

def vapor_pressure (baseline, reference, keys):
    """correction factor calculation code for

    float((wc_vapr * 1000) / ((cj_pres * cj_spfh) / (0.622 + 0.378 * cj_spfh)));

    Parameters
    ---------

    Returns
    -------
    """  
    r_vapor = keys['reference-vapor']
    b_pres = keys['baseline-pres']
    b_spfh = keys['baseline-spfh']

    ref = (reference[r_vapor] * 1000)     

    base = (
        (baseline[b_pres] * baseline[b_spfh]) / \
        (0.622 + 0.378 * baseline[b_spfh])
    )
    return ref/base


def radiation (baseline, reference, keys):
    """correction factor calculation code for
    float(((wc_srad * 1000) / (24 * 60 * 60)) / (cj_dswrf / (24 * 60 * 60))); 
    Parameters
    ---------

    Returns
    -------
    """  
    rk = keys['srad']
    bk = keys['dswrf']

    ref = (reference[rk] * 1000) /SECONDS_PER_DAY
    base = (baseline[bk] * 1000) /SECONDS_PER_DAY

    return ref/base


def wind_speed (baseline, reference, keys):
    """correction factor calculation code for

    float(wc_wind / sqrt(cj_ugrd^2 + cj_vgrd^2))

    Parameters
    ---------

    Returns
    -------
    """  
    r_wind = keys['reference-vapor']
    b_ugrd = keys['baseline-ugrd']
    b_vgrd = keys['baseline-vgrd']

    ref = reference[r_wind]   

    base = (baseline[b_ugrd]**2 + baseline[b_vgrd])**.5
    return ref/base


LOOKUP = {
    'temperature': temperature,
    'precipitation': precipitation
}

