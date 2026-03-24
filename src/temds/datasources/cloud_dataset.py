"""
Cloud Dataset
-------------

Provided an interface to create datasets from Google Earth Engine.
We are NOT maintaining it after the changes to the GEE quotas. The development 
was in a pretty rough state, so beware.
"""
from .dataset import TEMDataset, YearlyDataset
from temds.logger import Logger
from temds import gcloud_tools
import numpy as np
import time
from pathlib import Path

import xarray as xr
import rioxarray
from copy import deepcopy
from glob import glob

import shapely
import geopandas as gpd

import ee
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from . import era5_hourly_gee as era5

from temds.constants import SECONDS_PER_DAY, ZERO_C_IN_K

class CloudDataset(object):

    def __init__(self, dataset, bands, logger=Logger(), **kwargs):
        """
        Parameters
        ----------
        dataset: ee.ImageCollection or Dict of ee.ImageCollections with datetime keys
            The dataset to load. When loaded the object should be able to 
            pass the `verify` function
        logger: logger.Logger, defaults to new object
            Logger to use for printing or saving messages
            The default Logger will not print any messages, but a 
            text file may be created from it by calling `logger.save`
        **kwargs:
            Key word arguments passed to `load` 
        """
        self.dataset = ee.ImageCollection(dataset) # GEE image_collection i.e "ECMWF/ERA5_LAND/DAILY_AGGR"
        self.bands = bands # list or str, of bands in dataset
        self.vars = bands
        self.logger = logger
        self._cached_load_kwargs={}
        self.year = None
        if 'year' in kwargs:
            self.year = kwargs['year']


    @staticmethod
    def from_era5_hourly(year, ic=era5.IMAGE_COLLECTION_HOURLY, bands=era5.BANDS, logger=Logger()):
        """
        """
    
        new = CloudDataset(ic, ['tair_avg', 'prec', 'nirr', 'vapo'], year=year)

        ## only want data for `year`
        new.dataset = new.dataset.filterDate(
            f"{year}-01-01T00:00", f"{year+1}-01-01T00:00"
        ).select(era5.BANDS)
        
        def from_hourly(date):
            # day_of_year = ee.Number(n).add(1)
            start = ee.Date(date.strftime('%Y-%m-%d'))
            end = ee.Date((date + timedelta(days=1)).strftime('%Y-%m-%d'))
            daily = new.dataset.filter(ee.Filter.date(start,end )).sum()

            t2m = daily.select('temperature_2m').divide(24).subtract(ZERO_C_IN_K).rename('tair_avg') #daily_sum_k/24->avg_c, avg_k->c
            pr = daily.select('total_precipitation').multiply(1000).rename('prec') #daily_sum: m -> mm
            nirr =  daily.select('surface_solar_radiation_downwards').divide(SECONDS_PER_DAY).rename('nirr') # J/m^2 to W/m^2
            
            
            d2m = daily.select('dewpoint_temperature_2m').divide(24).subtract(ZERO_C_IN_K).rename('d2m')#daily_sum_k/24->avg_c, avg_k->c
            # 0.1 * 6.1078 * 10 ** ((era5['d2m'] * 7.5)/(era5['d2m'] + 237.3))
            vapo = d2m.expression('0.1 * 6.1078 * 10 ** ((d2m * 7.5)/(d2m + 237.3))', {'d2m':d2m.select('d2m')}).rename('vapo')
            # start = ee.Date(f'{year}-01-01').advance(n, 'days')
            daily = ee.Image([t2m, pr, nirr, vapo]).set('system:time_start', start.millis()).set( 'system:index', start.format('YYYYMMdd'))
            return daily
        
        monthly = {}
        for month in range(1,13):
            n_days = ((datetime(year,month,1) + relativedelta(months=1)) - datetime(year,month,1)).days
            days = [datetime(year,month,1) + timedelta(days=n) for n in range(n_days)]
            monthly[datetime(year,month,1)] = ee.ImageCollection([from_hourly(day) for day in days])

        new.dataset = monthly
        return new


    def download(self, where, bounds, credentials, filter_func=lambda x: x, name='temp-data', gdrive_location='colud_dataset_temp', gdrive_cached_id=None, local_cache=False):
        """
        """
        minx, maxx, miny, maxy = bounds[['minx','maxx','miny','maxy']].iloc[0]
        gee_aoi = ee.Geometry.BBox(minx, miny, maxx, maxy)
        print(minx, maxx, miny, maxy)
        len_files = 50
        # return
        if gdrive_cached_id is None and local_cache == False:
            if isinstance(self.dataset, ee.ImageCollection):
                tasks, files = self.export_image_collection(name, gdrive_location, gee_aoi, filter_func)
            else:
                tasks, files = self.export_dict(
                    name, gdrive_location, gee_aoi, filter_func
                )
            len_files = len(files)
            while np.array([task.status()['state'] != 'COMPLETED' for task in tasks]).any():
                if np.array([task.status()['state'] == 'FAILED' for task in tasks]).any():
                    raise ValueError('Check the cloud console for errors')
                status = [task.status()['state'] == 'COMPLETED' for task in tasks]
                n_tasks = len(status)
                n_complete = status.count(True)    
                print(f'waiting: {n_complete} of {n_tasks}')
                # print(status)
                time.sleep(100)


            parent_id = Path(tasks[0].status()['destination_uris'][0]).name
        else: 
            parent_id = gdrive_cached_id
        
        if local_cache == False:
            gdrive_files = gcloud_tools.list_files(credentials, parent_id, len_files*2)
            for file in gdrive_files:
                if not name in file['name']:
                    continue
                gcloud_tools.download_file(
                    credentials, file['id'], Path(where).joinpath(file['name'])
                )

        dataset = None
        for var in self.bands:
            var_data = []
            if hasattr(self, 'year'):
                glob_str = f'*{name}-{self.year}-*-{var}.tif'
            else:
                glob_str = f'*{name}-*-{var}.tif'
            for file in sorted(Path(where).glob(glob_str)):
                # print(file)
                var_data.append(rioxarray.open_rasterio(file))
            temp = xr.concat(var_data, dim='band')
            if dataset is None:
                dataset = xr.Dataset(
                    data_vars = { var : xr.DataArray(deepcopy(temp.values), dims=['time','y','x'])},
                    coords = {
                        'time': [datetime(2000,1,1) + timedelta(d) for d in range(temp.band.size)], 
                        'x':deepcopy(temp.x.values), 
                        'y':deepcopy(temp.y.values)
                    }
                )
            else:
                dataset[var] = xr.DataArray(deepcopy(temp.values), dims=['time','y','x'])

        dataset = dataset.rio.write_crs(temp.rio.crs,inplace=True)\
                    .rio.set_spatial_dims(x_dim='x', y_dim='x', inplace=True)\
                    .rio.write_coordinate_system(inplace=True)\
                    .rio.write_transform(temp.rio.transform(), inplace=True)
        
        return dataset
    
    
    def export_image_collection(self, name, gdrive_location, gee_aoi, filter_func=lambda x: x ):
        tasks = []
        files = []
        task_time = datetime.now().strftime("%Y%m%dT%H%M%S")
        for band in self.bands:
            daily = filter_func(self.dataset).select(band)
            merged = daily.toBands()
            merged.bandNames().size().getInfo()
            file_name = f'{task_time}-{name}-{band}'
            task = ee.batch.Export.image.toDrive(
                image=merged,
                description=file_name,
                folder= gdrive_location,
                region=gee_aoi,
                scale=4000,
                # crsTransform=[30, 0, -2493045, 0, -30, 3310005],
                crs='EPSG:6931'
            )
            task.start()
            tasks.append(task)
            files.append(f'{file_name}.tif')
        return tasks, files

    def export_dict(self, name, gdrive_location, gee_aoi, filter_func=lambda x: x ):
        tasks = []
        files = []
        task_time = datetime.now().strftime("%Y%m%dT%H%M%S")
        for month, ic in self.dataset.items():
            for band in self.bands:
                # print(month, band)
                daily = filter_func(ic).select(band)
                merged = daily.toBands()

                file_name = f'{task_time}-{name}-{month.strftime("%Y-%m")}-{band}'
                task = ee.batch.Export.image.toDrive(
                    image=merged,
                    description=file_name,
                    folder= gdrive_location,
                    region=gee_aoi,
                    scale=4000,
                    # crsTransform=[30, 0, -2493045, 0, -30, 3310005],
                    crs='EPSG:6931'
                )
                task.start()
                tasks.append(task)
                files.append(f'{file_name}.tif')

        return tasks, files
    
    
    def get_by_extent(self, minx, miny, maxx, maxy, extent_crs, **kwargs):
        """Returns xr.dataset for use in downscaling

        Parameters
        ----------
        minx: float
            Minimum x coord
        maxx: float
            Maximum x coord
        miny: float
            Minimum y coord
        maxy: float
            Maximum y coord
        extent_crs: crs.CRS
            crs of extent values
        **kwargs:
            'clip_with: str, defaults Gdal,
                flag to choose which clipping function to use
                'xarray' or 'gdal'
            'resolution': defaults, `resolution`
                resolution to use instead of `resolution`
            'resample_alg': defaults bilinear
                the resampling algorithm used by gdal
            'warp_no_data_as_array': bool, defaults False
                If true, the no data values are set 
                as an array, length of the number of bands, in gdal.Warp
            'gdal_type', int defaults gdal.GDT_Float32 
                gdal datatype
            'prime_warp': bool, defaults True
                When True primes gdal warp
        

        Returns
        -------
        TEMDataset
            subset of data from extent (`minx`,`miny`)(`maxx`,`maxy`)

        """
        creds = kwargs['credentials']
        bounds = gpd.GeoDataFrame(
            {'geometry': shapely.box(minx, miny,  maxx, maxy)}, 
            index=['aoi'],
            crs=extent_crs
        ).to_crs(4326).bounds
        print(bounds)

        where = kwargs['download_location'] if 'download_location' in kwargs else "temp-gdrive-downloads"
        gdrive_location = kwargs['gdrive_location'] if 'gdrive_location' in kwargs else "ee-exports-temds"
        name = kwargs['name']
        cached_id = kwargs['gcloud_cached_id'] if 'cached_id' in kwargs else None
        local_cache = kwargs['local_cache'] if 'local_cache' in kwargs else False
        where = Path(where)
        where.mkdir(exist_ok=True, parents=True)

        tile = self.download(
            where, 
            bounds, 
            creds, 
            # filter_date, 
            name=name,
            gdrive_location = gdrive_location,
            gdrive_cached_id = cached_id,
            local_cache=local_cache
        )
        # return tile
        dataset = TEMDataset(tile)

        if self.year:
            dataset = YearlyDataset.from_TEMDataset(dataset, self.year)

        return dataset 