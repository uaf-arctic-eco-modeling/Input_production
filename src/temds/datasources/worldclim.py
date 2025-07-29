"""
Worldclim
---------

Metadata for worldclim dataset

See: for dataset details (for v2.1) 
https://www.worldclim.org/data/worldclim21.html

"""
from cf_units import Unit

from temds import climate_variables

NAME = 'worldclim'


## citation for worldclim 2.1 dataset
CITATION = (
    'Fick, S.E. and R.J. Hijmans, 2017. WorldClim 2: new 1km spatial resolution' 
    ' climate surfaces for global land areas. International Journal of '
    ' Climatology 37 (12): 4302-4315.'
)


## REGISTER CLIMATE VARIABLES
climate_variables.register('tair_avg', NAME, 'tavg')
climate_variables.register('tair_min', NAME, 'tmin')
climate_variables.register('tair_max', NAME, 'tmax')
climate_variables.register('prec', NAME, 'prec')
climate_variables.register('nirr', NAME, 'srad')
climate_variables.register('wind', NAME, 'wind')
climate_variables.register('vapo', NAME, 'vapr')

## worldclim units are in downscale units except for
## srad/nirr 
climate_variables.register_source_unit('nirr', NAME, Unit('kJ m-2 day-1'))

VARS = climate_variables.aliases_for(NAME)

## these are degree seconds and degree minutes
## representing  form ~1 km2 to ~340 km2
RESOLUTIONS = ['30s', '2.5m', '5m', '10m']

class WorldclimURLError(Exception):
    """Raised if the url cannot be formatted"""
    pass

def name_for(variable, version='2.1', resolution='30s', month=None):
    if resolution not in RESOLUTIONS:
        raise WorldclimURLError('Invalid Resolution')

    if not variable in VARS:
        raise WorldclimURLError('Invalid variable')

    if month is None:
        return f'wc{version}_{resolution}_{variable}'
    else:
        return f'wc{version}_{resolution}_{variable}_{month:02d}'

def url_for(variable, version='2.1', resolution='30s'):
    v_us = version.replace('.','_')
    name = name_for(variable, version, resolution)
    return f'https://geodata.ucdavis.edu/climate/worldclim/{v_us}/base/{name}.zip'

