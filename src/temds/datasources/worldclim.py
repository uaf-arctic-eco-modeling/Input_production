"""
WorldClim
---------

Data structures representing WorldClim data

"""
from temds import climate_variables

## REGISTER CLIMATE VARIABLES
climate_variables.register('tair', 'worldclim', 'tavg')
climate_variables.register('tmin', 'worldclim', 'tmin')
climate_variables.register('tmax', 'worldclim', 'tmax')
climate_variables.register('prec', 'worldclim', 'prec')
climate_variables.register('nirr', 'worldclim', 'srad')
climate_variables.register('wind', 'worldclim', 'wind')
climate_variables.register('vapo', 'worldclim', 'vapr')

WORLDCLIM_VARS = climate_variables.aliases_for('worldclim')

## these are degree seconds and degree minutes
## representing  form ~1 km2 to ~340 km2
WORLDCLIM_RESOLUTIONS = ['30s', '2.5m', '5m', '10m']

class WorldclimURLError(Exception):
    """Raised if the url cannot be formatted"""
    pass

def worldclim_name_for(variable, version='2.1', resolution='30s', month=None):
    if resolution not in WORLDCLIM_RESOLUTIONS:
        raise WorldclimURLError('Invalid Resolution')

    if not variable in WORLDCLIM_VARS:
        raise WorldclimURLError('Invalid variable')

    if month is None:
        return f'wc{version}_{resolution}_{variable}'
    else:
        return f'wc{version}_{resolution}_{variable}_{month:02d}'

def worldclim_url_for(variable, version='2.1', resolution='30s'):
    v_us = version.replace('.','_')
    name = worldclim_name_for(variable, version, resolution)
    return f'https://geodata.ucdavis.edu/climate/worldclim/{v_us}/base/{name}.zip'

