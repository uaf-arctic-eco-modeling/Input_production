from .dataset import TEMDataset
from temds.logger import Logger
import numpy as np
import time

import ee

sample_dataset = "ECMWF/ERA5_LAND/DAILY_AGGR"
sample_bands=bands = ['temperature_2m', 'dewpoint_temperature_2m', 'total_precipitation_sum',  "surface_solar_radiation_downwards_sum", ]


class CloudDataset(TEMDataset):

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
        self.dataset = dataset # GEE image_collection i.e "ECMWF/ERA5_LAND/DAILY_AGGR"
        self.bands = bands # list or str, of bands in dataset
        self.logger = logger
        self._cached_load_kwargs={}


    def download(self, where, bounds, name='temp-data', grive_location='colud_dataset_temp'):
        
        ic = ee.ImageCollection(self.dataset)
        # gee_aoi=ee.Geometry.Rectangle([[a.x,a.y],[b.x,b.y]])
        
       
        minx, maxx, miny, maxy = bounds[['minx','maxx','miny','maxy']].iloc[0]
        gee_aoi = ee.Geometry.BBox(minx, miny, maxx, maxy)

        tasks = []
        files = []
        for band in self.bands:
            daily = ic.filterDate("2020-01-01T00:00", "2021-01-01T00:00").select(band)
            merged = daily.toBands()
            merged.bandNames().size().getInfo()
            file_name = f'{name}-{band}'
            task = ee.batch.Export.image.toDrive(
                image=merged,
                description=file_name,
                folder= grive_location,
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

