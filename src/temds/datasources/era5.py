"""
ERA 5
-----
metadata for ERA5 data

"""
import numpy as np
from cf_units import Unit

from temds import climate_variables 



NAME = 'ERA5'

IMAGE_COLLECTION_HOURLY = "ECMWF/ERA5/HOURLY"
# BANDS = ['temperature_2m', 'dewpoint_temperature_2m', 'total_precipitation_sum',  "surface_solar_radiation_downwards_sum", ]
BANDS=['temperature_2m', 'dewpoint_temperature_2m', 'total_precipitation', 'surface_solar_radiation_downwards']


CITATION = (

)



## REGISTER CLIMATE VARIABLES
climate_variables.register('tair_avg', NAME, 't2m')

climate_variables.register_source_unit('tair_avg', NAME, Unit('kelvin'))

climate_variables.register('prec', NAME, 'tp')
climate_variables.register_source_unit('prec', NAME, Unit('meters'))

climate_variables.register('nirr', NAME, 'ssrd')
climate_variables.register_source_unit('ssrd', NAME, Unit('J/m^2/day'))


climate_variables.register('dewpoint', NAME, 'd2m')
climate_variables.register_source_unit('dewpoint', NAME, Unit('kelvin'))

def calculate_vapo_from_dewpoint(d2m):
    """Calculate Vapor pressure from sea level pressure and
    specific humidity
    """
    return 0.1 * 6.1078 * 10 ** ((d2m * 7.5)/(d2m + 237.3))



