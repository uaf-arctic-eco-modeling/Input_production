"""
Climate Variables
-----------------

Metadata Management for TEM climate Variables


In the context of this file standard units refers
to the units used in downscaling process
"""
# from collections import namedtuple
from dataclasses import dataclass, field
from cf_units import Unit


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
@dataclass
class ClimateVariable:
    name: str
    abbr: str
    std_unit: Unit
    aliases: dict = field(default_factory=dict)
    source_units: dict = field(default_factory=dict)

# ClimateVariable = namedtuple('ClimateVariable', ['name', 'abbr', 'aliases'])

CLIMATE_VARIABLES = {
    ## FINAL downscaled variables
    'tair_avg': ClimateVariable('Average Air Temperature', 'tair_avg',  Unit('celsius')),
    'tair_max': ClimateVariable('Maximum Air Temperature', 'tair_max',  Unit('celsius')),
    'tair_min': ClimateVariable('Minimum Air Temperature', 'tair_min',  Unit('celsius')),
    'prec': ClimateVariable('Precipitation', 'prec', Unit('mm')), 
    'nirr': ClimateVariable('Radiation', 'nirr', Unit('W/m^2')), 
    'wind': ClimateVariable('Wind Speed', 'wind', Unit('m/s')), 
    'vapo': ClimateVariable('Vapor Pressure', 'vapo', Unit('kPa')), 
    'winddir': ClimateVariable('Wind Direction', 'winddir', Unit('degree')), ## CHECK if correct 
    ## Component Variables
    'ugrd': ClimateVariable('Zonal component of wind speed', 'ugrd', Unit('m/s')),
    'vgrd': ClimateVariable('Meridional component of wind speed', 'vgrd', Unit('m/s')),
    'spfh': ClimateVariable('Specific humidity', 'spfh', Unit('kg/kg')),
    'pres': ClimateVariable('Pressure', 'pres', Unit('Pa')),

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

def register_source_unit(cv, source, unit):
    """Registers an alias for a climate variable in CLIMATE_VARIABLES

    Parameters
    ----------
    cv: str
        climate variable in CLIMATE_VARIABLES
    source: str
        name of datasource
    unit: Unit
        Unit of source
    """
    CLIMATE_VARIABLES[cv].source_units[source] = unit

def temds_names():
    """returns a list of the variable names used in the TEMDS program

    Returns
    -------
    list[str]
    """
    return [cv.abbr for n,cv in CLIMATE_VARIABLES.items()]

def temds_units():
    """returns a list of the variable units used in the TEMDS program

    Returns
    -------
    list[Unit]
    """
    return [cv.std_unit for n,cv in CLIMATE_VARIABLES.items()]

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

def has_conversion(std_var, source):
    """Checks if conversion is present

    Parameters
    ----------
    std_var: str
        var in  CLIMATE_VARIABLES
    source: str
        datasource name

    Returns
    -------
    Bool
    """
    return source in CLIMATE_VARIABLES[std_var].source_units

def to_std_units(data, std_var, source):
    """convert data to standard units if conversion is present

    Parameters
    ----------
    data: np.array like
        data to convert
    std_var: str
        var in  CLIMATE_VARIABLES
    source: str
        datasource name

    Returns
    -------
    np.array like
        Converted data if data is preset, otherwise unchanged 
        data
    """
    if has_conversion(std_var, source):
        src_units = CLIMATE_VARIABLES[std_var].source_units[source]
        std_units = CLIMATE_VARIABLES[std_var].std_unit
        return src_units.convert(data, std_units)
    return data

def lookup_alias(source, alias):
    """looks up ClimateVariable based on source and 
    alias

    Parameters
    ----------
    source: str
        datasource name
    alias: str
        alias to lookup var for

    Raises
    ------
    KeyError:
        When alias is not present for the source

    Returns
    -------
    ClimateVariable
    """
    cvn = aliases_for(source, 'dict_r')[alias]
    return CLIMATE_VARIABLES[cvn]
    
