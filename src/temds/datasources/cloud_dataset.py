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
from datetime import datetime

from . import era5

class CloudDataset(object):

    def __init__(self, dataset, bands, logger=Logger(), **kwargs):
        """
        Parameters
        ----------
        dataset: xr.dataset or Path
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
        self.logger = logger
        self._cached_load_kwargs={}
        self.year = None
        if 'year' in kwargs:
            self.year = kwargs['year']


    @staticmethod
    def from_era5(year, ic=era5.IMAGE_COLLECTION, bands=era5.BANDS, logger=Logger()):
        new = CloudDataset(ic, bands)

        ## only want data for `year`
        new.dataset = new.dataset.filterDate(
            f"{year}-01-01T00:00", f"{year+1}-01-01T00:00"
        )

        
        try:
            datetime(year,2,29)
            new.dataset = new.dataset.filter(
                ee.Filter.Not(ee.Filter.date(f'{year}-02-29'))
            )

        except ValueError:
            pass # we dont need to remove leap day

        return new


    def download(self, where, bounds, credentials, filter_func=lambda x: x, name='temp-data', gdrive_location='colud_dataset_temp'):
        
        # ic = self.dataset
        # gee_aoi=ee.Geometry.Rectangle([[a.x,a.y],[b.x,b.y]])
        
       
        minx, maxx, miny, maxy = bounds[['minx','maxx','miny','maxy']].iloc[0]
        gee_aoi = ee.Geometry.BBox(minx, miny, maxx, maxy)

        tasks = []
        files = []
        for band in self.bands:
            daily = filter_func(self.dataset).select(band)
            merged = daily.toBands()
            merged.bandNames().size().getInfo()
            file_name = f'{name}-{band}'
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

        while np.array([task.status()['state'] != 'COMPLETED' for task in tasks]).any():
            if np.array([task.status()['state'] == 'FAILED' for task in tasks]).any():
                raise ValueError('Check the cloud console for errors')
            time.sleep(10)

        parent_id = Path(tasks[0].status()['destination_uris'][0]).name
        files = gcloud_tools.list_files(credentials, parent_id)
        for file in files:
            if not name in file['name']:
                continue
            gcloud_tools.download_file(
                credentials, file['id'], Path(where).joinpath(file['name'])
            )

        
        dataset = None
        for file in Path(where).glob(f'{name}*.tif'):
            print(file)
            temp = rioxarray.open_rasterio(file)
            name = '_'.join(temp.attrs['long_name'][0].split('_')[1:])
            if dataset is None:
                dataset = xr.Dataset(
                    data_vars = {name: xr.DataArray(deepcopy(temp.values), dims=['time','y','x'])},
                    coords={'time': deepcopy(temp.band.values), 'x':deepcopy(temp.x.values), 'y':deepcopy(temp.y.values)},
                )
            else:
                dataset[name] = xr.DataArray(deepcopy(temp.values), dims=['time','y','x'])

        dataset = dataset.rio.write_crs(temp.rio.crs,inplace=True)\
                    .rio.set_spatial_dims(x_dim='x', y_dim='x', inplace=True)\
                    .rio.write_coordinate_system(inplace=True)\
                    .rio.write_transform(temp.rio.transform(), inplace=True)
        
        return dataset
    
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



        tile = self.download(
            'test-cloud', 
            bounds, 
            creds, 
            # filter_date, 
            name='h06-v17', 
            gdrive_location='ee-sample-data'
        )
        
        dataset = TEMDataset(tile)

        if self.year:
            dataset = YearlyDataset.from_TEMDataset(dataset, self.year)

        return dataset 