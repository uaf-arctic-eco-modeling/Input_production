from .dataset import TEMDataset
from temds.logger import Logger
from temds import gcloud_tools
import numpy as np
import time
from pathlib import Path

import ee

sample_dataset = "ECMWF/ERA5_LAND/DAILY_AGGR"
sample_bands=bands = ['temperature_2m', 'dewpoint_temperature_2m', 'total_precipitation_sum',  "surface_solar_radiation_downwards_sum", ]


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

        