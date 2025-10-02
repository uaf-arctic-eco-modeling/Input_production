"""
ERA 5
-----
metadata for ERA5 data

"""
import numpy as np
from cf_units import Unit

from temds import climate_variables 



NAME = 'ERA 5'

IMAGE_COLLECTION = "ECMWF/ERA5_LAND/DAILY_AGGR"
BANDS = ['temperature_2m', 'dewpoint_temperature_2m', 'total_precipitation_sum',  "surface_solar_radiation_downwards_sum", ]



CITATION = (

)



## REGISTER CLIMATE VARIABLES
climate_variables.register('tair_avg', NAME, 'TODO')
climate_variables.register('prec', NAME, 'TODO')
climate_variables.register('nirr', NAME, 'TODO')
climate_variables.register('spfh', NAME, 'TODO')
climate_variables.register('psl', NAME, 'TODO')