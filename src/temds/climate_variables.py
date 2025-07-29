"""
Climate Variables
-----------------

Metadata Management for TEM climate Variables
"""
from collections import namedtuple

## ClimateVariable  namedtuple type
## 
## Attributes
## ----------
## name: str
##    descriptive name of variable
## abbr: str
##    abbreviation used in final TEM downscaled data     
## aliases: dict{str: str} 
##    aliases for each data source
ClimateVariable = namedtuple('ClimateVariable', ['name', 'abbr', 'aliases'])

CLIMATE_VARIABLES = {
    ## FINAL downscaled variables
    'tair': ClimateVariable('Average Air Temperature', 'tair', {}),
    'tmax': ClimateVariable('Max Air Temperature', 'tmax', {}),
    'tmin': ClimateVariable('Minimum Air Temperature', 'tmin', {}),
    'prec': ClimateVariable('Precipitation', 'prec', {}), 
    'nirr': ClimateVariable('Radiation', 'nirr', {}), 
    'wind': ClimateVariable('Wind Speed', 'wind', {}), 
    'vapo': ClimateVariable('Vapor Pressure', 'vapo', {}), 
    'winddir': ClimateVariable('Wind Direction', 'winddir', {}), 
    ## Component Variables
    'ugrd': ClimateVariable('CRUJRA  Wind Direction U Component', 'ugrd', {}),
    'vgrd': ClimateVariable('CRUJRA Wind Direction V Component', 'vgrd', {}),
    'spfh': ClimateVariable('spfh', 'spfh', {}),
    'pres': ClimateVariable('pres', 'pres', {}),

}

def register(cv, source, alias):
    """Registers an alias for a climate variable in CLIMATE_VARIABLES

    Parameters
    ----------
    cv: str
        climate variable in CLIMATE_VARIABLES
    source: str
        name of datasource
    alias: str
        variable alias for source
    """
    CLIMATE_VARIABLES[cv].aliases[source] = alias

def list_for(source: str):
    """Returns sources registered ClimateVariables as a list

    Parameters
    ----------
    source: str
        a source i.e worldclim, crujra

    Returns
    -------
    list[ClimateVariable]
    """
    return [
        CLIMATE_VARIABLES[n] for n in CLIMATE_VARIABLES \
        if source in CLIMATE_VARIABLES[n].aliases
    ]

def aliases_for(source: str, _as: str='list'):
    """Returns sources aliases as a list or dict

    Parameters
    ----------
    source: str
        a source i.e worldclim, crujra
    _as: str, default 'list'
        'list' or 'dict' or, 'dict_r' which determines type to return
        'dict_r' is a dict with the key/values reversed

    Returns
    -------
        list[str]
    or 
        dict{str: str}
    """
    if _as == 'dict':
        return {cv.abbr: cv.aliases[source] for cv in list_for(source)}
    elif _as == 'dict_r':
        return {cv.aliases[source]: cv.abbr for cv in list_for(source)}
    else:
        return [cv.aliases[source] for cv in list_for(source)]
