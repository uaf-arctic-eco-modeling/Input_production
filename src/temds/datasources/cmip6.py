"""
CMIP 6
------
metadata for cmip6 data

"""
import numpy as np
from cf_units import Unit

from temds import climate_variables 
from temds.constants import SECONDS_PER_DAY


NAME = 'CMIP 6'


CITATION = (

)


## REGISTER CLIMATE VARIABLES
climate_variables.register('tair_avg', NAME, 'tas')
climate_variables.register('prec', NAME, 'pr')
climate_variables.register('nirr', NAME, 'rsds')
climate_variables.register('spfh', NAME, 'huss')
climate_variables.register('pres', NAME, 'psl')

climate_variables.register_source_unit('tair_avg', NAME, Unit('kelvin'))

## the source unit is kg m-2 s-2 which i think is the same as mm/s
## so this should work
climate_variables.register_source_unit('prec', NAME, Unit(f'{SECONDS_PER_DAY} mm'))

VARS = climate_variables.aliases_for(NAME)
SOURCE_VARS = [v for v in VARS if v not in []]


DEFAULT_EXPERIMENTS = ['historical', 'ssp126', 'ssp245', 'ssp370', 'ssp585']
DEFAULT_ENSEMBLES = ['r1i1p1f1']  # was 'r1i1p1f1_gn' what is gn?
DEFAULT_MODELS=['ACCESS-CM2','MRI-ESM2-0']

