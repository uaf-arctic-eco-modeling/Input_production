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
climate_variables.register('tair_avg', NAME, 'temperature_2m')
climate_variables.register('prec', NAME, 'total_precipitation')

# climate_variables.register('dewpoint', NAME, 'dewpoint_temperature_2m')



climate_variables.register('nirr', NAME, 'TODO')
climate_variables.register('spfh', NAME, 'TODO')
climate_variables.register('psl', NAME, 'TODO')