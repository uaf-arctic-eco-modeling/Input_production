"""
Downscaled
----------

Objects representing downscaled data
"""
import xarray as xr
from . import annual


DOWNSCALED_VARIABLES = {
    'tavg': 'tair_oC',
    'tmin': 'tmin_oC',
    'tmax': 'tmax_oC',
    'prec': 'prec_mm',
    'vapo': 'vapo_Pa',
    'nirr': 'nirr_Wm2',
    'wdir': 'winddir_deg',
    'wspd': 'wind_ms'
    

}

class AnnualTimeSeries(annual.AnnualTimeSeries):
    """
    """
    pass


class AnnualDaily(annual.AnnualDaily):
    """CUR JRA resampled data daily for a year, This class 
    assumes data for a single year in input file
    """
    def __init__ (self, year, in_data, verbose=False, _vars=[],  **kwargs):

        super().__init__(year, in_data, verbose, _vars,  **kwargs)
    
    def synthesize_to_monthly(self, _vars):
        """
        """
        monthly = []

        for var in _vars:
            thing = 'some action'
            monthly.append(thing)

        monthly = xr.concat(monthly, dim='time')

        