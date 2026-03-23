"""
CDS API Tools
-------------

tools for downloading CDS API data(i.e. era5, cmip6)
"""
from pathlib import Path

from ecmwf.datastores import Client

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


def download_era5_daily(where, years, bounds, variables, logger=None):
    collection_id = "derived-era5-single-levels-daily-statistics"
    where = Path(where)
    print(f'Downloading {collection_id }')
    for year in years:
        print(f'.. for {year}')
        for var, stat in variables.items():
            print(f'.... for {var} - {stat}')
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
            download(where/f'{year}-{var}.nc', collection_id, request)
