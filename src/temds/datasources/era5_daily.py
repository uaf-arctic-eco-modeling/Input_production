"""
ERA 5
-----
metadata for ERA5 data

TODO: 
    - better bounds handling, like this is an issue across many files, 
    and it should be done consistently
    - kwarg to handle other request params
    - checks of data before merge, i.e for all vars to be present 
"""
from pathlib import Path

# import numpy as np
import xarray as xr
from cf_units import Unit

from .. import climate_variables 
from .. import cdsapi_tools 

from .dataset import YearlyDataset



NAME = 'ERA5_DAILY'

COLLECTION_ID = "derived-era5-single-levels-daily-statistics"

CITATION = """
In addition to the requirements of the applicable license(s), users must:

    cite the CDS catalogue entry;
    provide clear and visible attribution to the Copernicus programme and 
    attribute each data product used;


Citing the CDS catalogue entry:
    Copernicus Climate Change Service, Climate Data Store, (2024): ERA5 
    post-processed daily-statistics on single levels from 1940 to present. 
    Copernicus Climate Change Service (C3S) Climate Data Store (CDS), 
    DOI: 10.24381/cds.4991cf48 (Accessed on DD-MMM-YYYY)

 
Attribution:

Copernicus programme:
    [Generated using/Contains modified] Copernicus Climate Change Service 
    information [year]. Neither the European Commission nor ECMWF is responsible
    for any use that may be made of the Copernicus information or data it
    contains.

Data:
    Hersbach, H., Comyn-Platt, E., Bell, B., Berrisford, P., Biavati, G.,
    Horányi, A., Muñoz Sabater, J., Nicolas, J., Peubey, C., Radu, R., 
    Rozum, I., Schepers, D., Simmons, A., Soci, C., Dee, D., Thépaut, J-N., 
    Cagnazo, C., Cucchi, M. (2023): ERA5 post-processed daily-statistics on 
    pressure levels from 1940 to present. Copernicus Climate Change Service 
    (C3S) Climate Data Store (CDS), DOI: 10.24381/cds.4991cf48 
    (Accessed on DD-MMM-YYYY)
"""

DOI = "10.24381/cds.4991cf48"

API_VARIABLES = {
    'dewpoint': {
        "name": "2m_dewpoint_temperature",
        "statistic": "daily_mean",
    },
    'tair_avg': {
        "name": "2m_temperature",
        "statistic": "daily_mean",
    },
    'nirr': {
        "name": "surface_solar_radiation_downwards",
        "statistic": "daily_sum"
    },
    'prec': {
        "name": "total_precipitation",
        "statistic": "daily_sum"
    },
   
}

DEFAULT_BOUNDS = [90, -180, 30, 180]

## REGISTER CLIMATE VARIABLES
climate_variables.register('tair_avg', NAME, 't2m')

climate_variables.register_source_unit('tair_avg', NAME, Unit('kelvin'))

climate_variables.register('prec', NAME, 'tp')
climate_variables.register_source_unit('prec', NAME, Unit('meters'))

climate_variables.register('nirr', NAME, 'ssrd')
climate_variables.register_source_unit('nirr', NAME, Unit('J/m^2/day'))


climate_variables.register('dewpoint', NAME, 'd2m')
climate_variables.register_source_unit('dewpoint', NAME, Unit('kelvin'))

def calculate_vapo_from_dewpoint(d2m):
    """Calculate Vapor pressure dew point
    """
    return 0.1 * 6.1078 * 10 ** ((d2m * 7.5)/(d2m + 237.3))



def download_variable_for_year_month(
        where: Path | str, variable: str, year: int, month: int,
        bounds:tuple=DEFAULT_BOUNDS, overwrite:bool=False
    ):
    """Download data for a variable and year from ecmwf using api

    Parameters
    ----------
    where: Path or str
        Path to directory to save file in
    variable: str
        TEMDS standard variable name in API_VARIABLES
    year: int 
        a year from 1940 to present
    month: int
        month from 1 - 12 
    bounds: tuple, default DEFAULT_BOUNDS
        bounds as a tuple in format [max lat, min lon, min lat, max lon]
    overwrite: Bool, default False 
        If true overwrite downloads, otherwise don't

    Returns
    -------
    Path, status
        Path is path to file.
        status, is complete, skipped, or failed
    """
    where = Path(where)
    api_var = API_VARIABLES[variable]['name']
    api_stat = API_VARIABLES[variable]['statistic']
    request = {
        "product_type": ["reanalysis"],
        "variable": [api_var],
        "year": [f"{year}"],
        "month": [f'{month:02}'],
        "day": [f'{d:02}' for d in range(1,32)],
        "daily_statistic": api_stat,
        "time_zone": "utc+00:00",
        "frequency": "1_hourly",
        "area": bounds,
        "data_format": "netcdf",
        # "download_format": "zip",
    }
    save_to = where/f'{year}-{month:02}-{api_var}.nc'
    try:
        if not save_to.exists() or overwrite:
            cdsapi_tools.download(save_to, COLLECTION_ID, request)
            status = 'complete'
        else: 
            status = 'skipped'
    except: 
        status = 'failed'
    
    return save_to, status

def merge_for_year(year: int, datasets: list[xr.Dataset]):
    """Merge all variables for a given year.

    Parameters
    ----------
    year: int 
        a year from 1940 to present
    datasets: list[xr.dataset]
        list datasets with items for each variable in API_VARIABLES
    source: str

    Returns
    -------
    YearlyDataset
    """
    source=NAME # this may be useful as an argument at some point, if this 
    #code were to be reused 

    merged = xr.merge(datasets)

    for std_name, src_name in climate_variables.aliases_for(source, 'dict').items():
        if climate_variables.has_conversion(std_name, source):
            merged[src_name].values = climate_variables.to_std_units(
                merged[src_name].values, std_name, source
            )
            cv = climate_variables.lookup_alias(source, src_name)
            unit = cv.std_unit.name
            v_name = cv.name
            merged[src_name].attrs.update(units=unit, name=v_name)

    rename_dict = climate_variables.aliases_for(source, 'dict_r')
    rename_dict.update({'longitude':'lon', 'latitude':'lat', 'valid_time':'time'})
    merged = merged.rename(rename_dict)
    
    d2m = merged['dewpoint']
    merged['vapo'] = calculate_vapo_from_dewpoint(d2m)
    unit = climate_variables.CLIMATE_VARIABLES['vapo'].std_unit.name
    v_name = climate_variables.CLIMATE_VARIABLES['vapo'].name
    merged['vapo'].attrs.update(units=unit, name=v_name)


    merged.rio.write_crs('EPSG:4326',inplace=True)\
        .rio.set_spatial_dims(x_dim='lon', y_dim='lat', inplace=True)

    merged = YearlyDataset(year, merged)


    return merged
