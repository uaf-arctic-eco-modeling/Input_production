"""
CRU JRA
-------

Data structures representing CRU JRA data
"""
import numpy as np
from cf_units import Unit

from temds import climate_variables 
from temds.constants import SECONDS_PER_DAY

NAME = 'crujra'


## Recommended citation for v2.5
CITATION = (
    "University of East Anglia Climatic Research Unit; Harris, I.C. (2024): "
    "CRU JRA v2.5: A forcings dataset of gridded land surface blend of Climatic "
    "Research Unit (CRU) and Japanese reanalysis (JRA) data; "
    "Jan.1901 - Dec.2023.. NERC EDS Centre for Environmental Data Analysis, "
    "date of citation. "
    "https://catalogue.ceda.ac.uk/uuid/43ce517d74624a5ebf6eec5330cd18d5"
)

## TODO move this to somewhere else
import geopandas as gpd 
from shapely.geometry import Point, MultiPoint

a = Point(-180.0, 44.930151)
b = Point(180.0, 84.223125)
ARCTIC_BOUNDS = gpd.GeoDataFrame( {'geometry': MultiPoint([a, b])}, index=['arctic']).bounds.loc['arctic']

## REGISTER CLIMATE VARIABLES
climate_variables.register('tair_avg', NAME, 'tmp')
climate_variables.register('tair_min', NAME, 'tmin')
climate_variables.register('tair_max', NAME, 'tmax')
climate_variables.register('prec', NAME, 'pre')
climate_variables.register('nirr', NAME, 'dswrf')
climate_variables.register('ugrd', NAME, 'ugrd')
climate_variables.register('vgrd', NAME, 'vgrd')
climate_variables.register('spfh', NAME, 'spfh')
climate_variables.register('pres', NAME, 'pres')

## this var is not present in raw data and has to be
## calculated from spfh and pres
climate_variables.register('vapo', NAME, 'vapo')
climate_variables.register('wind', NAME, 'wind')
climate_variables.register('winddir', NAME, 'winddir')

climate_variables.register_source_unit('tair_avg', NAME, Unit('celsius'))
climate_variables.register_source_unit('tair_min', NAME, Unit('celsius'))
climate_variables.register_source_unit('tair_max', NAME, Unit('celsius'))
climate_variables.register_source_unit('nirr', NAME, Unit(f'{ 1/SECONDS_PER_DAY} kilogram-second^-3'))

VARS = climate_variables.aliases_for(NAME)
SOURCE_VARS = [v for v in VARS if v not in ['vapo', 'wind', 'winddir']]

RESAMPLE_LOOKUP = {
    'tmin': 'mean',
    'tmax': 'mean',
    'tmp': 'mean',
    'pre': 'sum',  
    'dswrf': 'sum',
    'ugrd': 'mean',
    'vgrd': 'mean',
    'spfh': 'mean',
    'pres': 'mean',
    
}



def calculate_vapo(pres, spfh):
    """
    
    """
    return (0.001 * pres * spfh) / (0.622 + 0.378 * spfh)

def calculate_wind(ugrd, vgrd):
    """"""
    ## pythagorean theorem
    return np.sqrt((ugrd ** 2) + (vgrd**2))


def calculate_winddir(ugrd, vgrd):
    """"""
    return (360.0/2.0) * (1 + (ugrd/np.abs(ugrd))) + \
           ((180.0/np.pi)*np.atan2(ugrd,vgrd))


def name_for(variable, year, version='2.5'):
    """I think the other fields(5d is .5degree cell 365d is
    the n days) are not changing for our purposes
    """
    name = f'crujra.v{version}.5d.{variable}.{year}.365d.noc'
    return name

def url_for(variable, version='2.5'):
    raise NotImplementedError('Need to reimplement(implement?) download')
    file_format = '{var}/crujra.v2.5.5d.{var}.{yr}.365d.noc.nc.gz'
    return url