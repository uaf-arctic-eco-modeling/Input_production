"""
CDS API Tools
-------------

tools for downloading CDS API data(i.e. era5, cmip6)
"""
from pathlib import Path

from ecmwf.datastores import Client
import xarray as xr
from .datasources import dataset, era5
from . import climate_variables
from .constants import SECONDS_PER_DAY, ZERO_C_IN_K

DEFAULT_VARIABLES = {
    "2m_dewpoint_temperature":  "daily_mean",
    "2m_temperature":  "daily_mean",
    "total_precipitation":  "daily_sum",
    "surface_solar_radiation_downwards":  "daily_sum",
}
DEFAULT_BOUNDS = [90, -180, 30, 180]

def download(where, collection_id,  request):
    client = Client()
    client.retrieve(collection_id, request, target=where) 



def merge_for_year(year, files, source=era5.NAME, cleanup=True, logger=None):
    
    yearly_data = [xr.open_dataset(file) for file in files]
    merged = xr.merge(yearly_data)


    for std_name, src_name in climate_variables.aliases_for(source, 'dict').items():
        if climate_variables.has_conversion(std_name, source):
            # logger.info(f'{func_name}: converting units for {src_name} to {std_name}')
            merged[src_name].values = climate_variables.to_std_units(
                merged[src_name].values, std_name, source
            )
            cv = climate_variables.lookup_alias(source, src_name)
            unit = cv.std_unit.name
            v_name = cv.name
            merged[src_name].attrs.update(units=unit, name=v_name)

    rename_dict = climate_variables.aliases_for(source, 'dict_r')
    rename_dict.update({'longitude':'lon', 'latitude':'lat'})
    merged = merged.rename(rename_dict)
    
    d2m = merged['dewpoint']
    merged['vapo'] = era5.calculate_vapo_from_dewpoint(d2m)
    unit = climate_variables.CLIMATE_VARIABLES['vapo'].std_unit.name
    v_name = climate_variables.CLIMATE_VARIABLES['vapo'].name
    merged['vapo'].attrs.update(units=unit, name=v_name)


    merged.rio.write_crs('EPSG:4326',inplace=True)\
        .rio.set_spatial_dims(x_dim='lon', y_dim='lat', inplace=True)

    merged = dataset.YearlyDataset(year, merged)

    [ds.close() for ds in yearly_data]
    if cleanup:
        [file.unlink(file) for file in files]
    return merged


def download_era5_daily(where, years, bounds, variables, overwrite=False, logger=None, temp_dir = None, keep_temp=False):
    collection_id = "derived-era5-single-levels-daily-statistics"
    where = Path(where)
    if temp_dir is None:
        temp_dir = where
    temp_dir = Path(temp_dir)

    print(f'Downloading {collection_id }')
    for year in years:
        print(f'.. for {year}')
        yearly_files = []
        for var, stat in variables.items():
            
            request = {
                "product_type": ["reanalysis"],
                "variable": [var],
                "year": [f"{year}"],
                "month": [f'{mn:02}' for mn in range(1,13)],
                "day": [f'{d:02}' for d in range(1,32)],
                "daily_statistic": stat,
                "time_zone": "utc+00:00",
                "frequency": "1_hourly",
                "area": bounds,
                "data_format": "netcdf",
                # "download_format": "zip",
            }
            save_to = temp_dir/f'{year}-{var}.nc'
            if not save_to.exists() or overwrite:
                print(f'.... for {var} - {stat}') 
                download(save_to, collection_id, request)
            else:
                print(f'.... for {var} - {stat} - file exists skipping download')
                yearly_files.append(save_to)

        
        # merged = merge_yearly(year, yearly_files, not keep_temp)
        
        # merged.save(where/f'daily-ERA5-{year}.nc', overwrite=overwrite)

        