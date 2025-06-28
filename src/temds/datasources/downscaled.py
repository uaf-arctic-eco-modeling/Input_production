"""
Downscaled
----------

Objects representing downscaled data
"""
import xarray as xr

from temds import climate_variables
from . import annual


## REGISTER CLIMATE VARIABLES
climate_variables.register('tair', 'downscaled', 'tair_oC')
climate_variables.register('tmin', 'downscaled', 'tmin_oC')
climate_variables.register('tmax', 'downscaled', 'tmax_oC')
climate_variables.register('prec', 'downscaled', 'prec_mm')
climate_variables.register('nirr', 'downscaled', 'nirr_Wm2')
climate_variables.register('vapo', 'downscaled', 'vapo_Pa')
climate_variables.register('wind', 'downscaled', 'wind_ms')
climate_variables.register('winddir', 'downscaled', 'winddir_deg')

DOWNSCALED_VARIABLES = climate_variables.aliases_for('downscaled')


class AnnualTimeSeries(annual.AnnualTimeSeries):
    """
    """
    pass


class AnnualDaily(annual.AnnualDaily):
    """CRU JRA resampled data daily for a year, This class 
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

        