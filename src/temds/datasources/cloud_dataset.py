"""
Cloud Dataset
-------------

Earth Engine cloud based dataset object

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
from threading import Thread


import xarray as xr
import rioxarray
from copy import deepcopy
from glob import glob


import shapely
import geopandas as gpd
from affine import Affine
from pyproj import CRS

import ee
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from . import errors
from . import era5_hourly_gee as era5

from temds.constants import SECONDS_PER_DAY, ZERO_C_IN_K

class CloudDataset(object):
    """
    Attributes
    ----------
    dataset: ee.ImageCollection
        EE image collection for dataset
    bands: list or str
        bands in dataset
    vars: list or str 
        alias of bands
    logger: Logger
        Logger to use for printing or saving messages
    year: int or None
        int if year is associated with data
        None Otherwise
    _cached_load_kwarg: dict
    """
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
        """Create CloudDataset with daily data for a given year from ear5 
        Hourly data

        Parameters
        ----------
        year: int
            year of data
        ic: str
            use "ECMWF/ERA5/HOURLY", others not tested, but may work
        bands: list
            list of bands in `ic`
        logger: logger.Logger, defaults to new object
            Logger to use for printing or saving messages
            The default Logger will not print any messages, but a 
            text file may be created from it by calling `logger.save`

        Returns
        -------
        CloudDataset:
            with `dataset` initialized to supply daily data for `ic`
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


    def download(self, where, bounds, credentials, **kwargs):
        """Download for provided bounds data to TEMDataset

        Parameters
        ----------
        where: path
            path to download temp data to
        bounds: GeoDataFrame
            Bounds from first row are used
        credentials: Credentials
            Google cloud credentials
        name: str, Optional
            Name to use for files
        filter_func: Lambda Function, Optional
            function to filter ee.ImageCollection objects
            Default function is a passthrough function
        
        gdrive_location: str
            name of folder to use on gdrive
        gdrive_cached_id: str, or None, Defaults None
            id of folder on drive with pre-calculated data
            if provided data is downloaded from drive folder
        local_cache: bool, default False
            When True, skip EE and Drive protions of code and use 
            data in `where`
        clean_up_gdrive: bool, Default False
            Option to clean up files in gdrive after download by
            moving them to gdrive trash

        Returns
        -------
        xr.dataset
        """
        parameters = {
            'filter_func': lambda x: x, 
            'name': 'CloudDataset-temp', 
            'gdrive_location': 'CloudDataset-temp', 
            'gdrive_cached_id': None, 
            'local_cache': False, 
            'clean_up_gdrive': False,
            'crs': CRS('EPSG:4326'),
            'resolution': None, #.5degree for wgs84
        }
        parameters.update(kwargs)
        parameters['crs'] = CRS(parameters['crs'])
        # print(parameters)

        name = parameters['name']

        minx, maxx, miny, maxy = bounds[['minx','maxx','miny','maxy']].iloc[0]
        geojson_object = {
            "type": "Polygon", 
            "coordinates": [
                list(shapely.box(minx,miny, maxx,maxy).exterior.coords)
            ],
        }
        resolution = parameters['resolution']
        crs = parameters['crs']
        ## if not provided assume wgs84 which is ee defaut
        if parameters['crs'] == CRS('EPSG:4326'):
            gee_aoi=ee.Geometry(geojson_object)
            if resolution  is None:
                resolution = .5
        else:
            # crs = parameters['crs'].to_espg()
            gee_aoi=ee.Geometry(geojson_object, ee.Projection(f'EPSG:{crs.to_epsg()}'), False, True)
            if resolution  is None:
                resolution = 4000


        transform = [resolution, 0, minx, 0,  -resolution, maxy]
        # print(transform)

        len_files = 50
        # return
        gdrive_location = parameters['gdrive_location']
        filter_func = parameters['filter_func']
        gdrive_cached_id = parameters['gdrive_cached_id']
        local_cache = parameters['local_cache']
        clean_up_gdrive = parameters['clean_up_gdrive']
        
        threads = []
        if gdrive_cached_id is None and local_cache == False:
            print('CloudDataset: Submitting task to GEE')
            tasks, files = self.export_gee(
                name, gdrive_location, gee_aoi, crs, transform, filter_func
            )
            downloaded = [False for i in tasks]
            tasks_statuses = [task.status()['state'] != 'COMPLETED' for task in tasks]
            print('CloudDataset: Waiting for GEE to complete')
            while np.array(tasks_statuses).any() or (~np.array(downloaded)).any():
                if np.array([task.status()['state'] == 'FAILED' for task in tasks]).any():
                    raise ValueError('Check the cloud console for errors')
                status = [task.status()['state'] == 'COMPLETED' for task in tasks]
                n_tasks = len(status)
                n_complete = status.count(True)    
                print(f'CloudDataset: waiting - {n_complete} of {n_tasks}')
                for tn in range(n_tasks):
                    ct = tasks[tn].status()
                    if ct['state'] == 'COMPLETED' and not downloaded[tn]:
                        print(f'CloudDataset: downloading item:{tn+1}')
                        parent_id = Path(ct['destination_uris'][0]).name
                        f_name = ct['description'] + '.tif'
                        results = gcloud_tools.search(credentials, f"'{parent_id}' in parents and name = '{f_name}'")['files']
                        results = [r for r in results if not r['trashed']]
                        if len(results) > 1:
                            self.logger.warn(f'Multiple files named {f_name}, using first, could produce incorrect results')
                        gc_id = results[0]['id']

                        t = Thread(
                            target=gcloud_tools.download_file, 
                            args=[credentials, gc_id, Path(where).joinpath(f_name)]
                        )
                        t.start()
                        threads.append(t)
                        downloaded[tn] = True
                        if clean_up_gdrive:
                            gcloud_tools.trash_file(credentials, gc_id)
            
                if (n_tasks - n_complete) > 5:
                    time.sleep(60)
                else:
                    time.sleep(10)
                tasks_statuses = [task.status()['state'] != 'COMPLETED' for task in tasks]
            parent_id = Path(tasks[0].status()['destination_uris'][0]).name
        elif local_cache == False: 
            ## NOT TESTED
            parent_id = gdrive_cached_id
            gdrive_files = gcloud_tools.list_files(credentials, parent_id, len_files*2)
            for file in gdrive_files:
                if not name in file['name']:
                    continue
                t = Thread(
                    target=gcloud_tools.download_file, 
                    args=[credentials, file['id'], Path(where).joinpath(file['name'])]
                )
                t.start()
                threads.append(t)
                # gcloud_tools.download_file(
                #     credentials, file['id'], Path(where).joinpath(file['name'])
                # )
                if clean_up_gdrive:
                    gcloud_tools.trash_file(credentials, file['id'])

        ## wait for downloads to complete
        [t.join() for t in threads]

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
                        'time': [datetime(self.year,1,1) + timedelta(d) for d in range(temp.band.size)], 
                        'y':deepcopy(temp.y.values),
                        'x':deepcopy(temp.x.values) 
                        
                    }
                )
            else:
                dataset[var] = xr.DataArray(deepcopy(temp.values), dims=['time','y','x'])

        dataset = dataset.rio.write_crs(temp.rio.crs,inplace=True)\
                    .rio.set_spatial_dims(x_dim='x', y_dim='y', inplace=True)\
                    .rio.write_coordinate_system(inplace=True)\
                    .rio.write_transform(temp.rio.transform(), inplace=True)    
        return dataset
    
    def export_gee(self, name, gdrive_location, gee_aoi, 
                   crs, transform, filter_func=lambda x: x
                   ):
        if isinstance(self.dataset, ee.ImageCollection):
            tasks, files = CloudDataset.export_image_collection(
                self.dataset, self.bands, 
                name, gdrive_location, gee_aoi, crs, transform, filter_func
            )
        else:
            tasks, files = [], []
            for month, ic in self.dataset.items():
                loop_name = f'{name}-{month.strftime("%Y-%m")}'
                t_temp, f_temp = CloudDataset.export_image_collection(
                    ic, self.bands, 
                    loop_name, gdrive_location, gee_aoi, crs, transform, filter_func
                )
                tasks += t_temp
                files += f_temp
        return tasks, files


    @staticmethod
    def export_image_collection(ic, gee_bands, name, gdrive_location, gee_aoi, crs, transform, filter_func=lambda x: x ):
        """
        export from ee if `dataset` is ee.ImageCollection
        
        Parameters
        ----------
            name: str
                name for files
            gdrive_location: str
                folder on Google Drive
            gee_aoi: ee.Geometry.BBox
                AOI formatted for EE
            filter_func: Lambda Function, Optional
                function to filter ee.ImageCollection objects
                Default is passthrough function

        Returns
        -------
        tasks: list
            list of ee tasks
        files: list
            names of files generated
        """
        tasks = []
        files = []
        task_time = datetime.now().strftime("%Y%m%dT%H%M%S")
        for band in gee_bands:
            daily = filter_func(ic).select(band)
            merged = daily.toBands()
            merged.bandNames().size().getInfo()
            file_name = f'{task_time}-{name}-{band}'
            task = ee.batch.Export.image.toDrive(
                image=merged,
                description=file_name,
                folder= gdrive_location,
                region=gee_aoi,
                # scale=4000,
                crsTransform=transform,#[30, 0, -2493045, 0, -30, 3310005],
                crs=f'EPSG:{crs.to_epsg()}',
            )
            task.start()
            tasks.append(task)
            files.append(f'{file_name}.tif')
        return tasks, files

    # def export_dict(self, name, gdrive_location, gee_aoi, transform, filter_func=lambda x: x ):
    #     """
    #     export from ee if `dataset` is  Dict of ee.ImageCollections with datetime keys
        
    #     Parameters
    #     ----------
    #         name: str
    #             name for files
    #         gdrive_location: str
    #             folder on Google Drive
    #         gee_aoi: ee.Geometry.BBox
    #             AOI formatted for EE
    #         filter_func: Lambda Function, Optional
    #             function to filter ee.ImageCollection objects
    #             Default is passthrough function

    #     Returns
    #     -------
    #     tasks: list
    #         list of ee tasks
    #     files: list
    #         names of files generated
    #     """
    #     tasks = []
    #     files = []
    #     task_time = datetime.now().strftime("%Y%m%dT%H%M%S")
    #     for month, ic in self.dataset.items():
    #         for band in self.bands:
    #             # print(month, band)
    #             daily = filter_func(ic).select(band)
    #             merged = daily.toBands()

    #             file_name = f'{task_time}-{name}-{month.strftime("%Y-%m")}-{band}'
    #             task = ee.batch.Export.image.toDrive(
    #                 image=merged,
    #                 description=file_name,
    #                 folder= gdrive_location,
    #                 region=gee_aoi,
    #                 # scale=4000,
    #                 crsTransform=transform,#[30, 0, -2493045, 0, -30, 3310005],
    #                 crs='EPSG:6931'
    #             )
    #             task.start()
    #             tasks.append(task)
    #             files.append(f'{file_name}.tif')

    #     return tasks, files
    
    
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
            'credentials': Credentials, required
                Google cloud Credentials 
            'task_name': str, required
                task name for ee task
            'download_location': Path, Defaults "ee-exports-temds"
            'gdrive_location': str, defaults "ee-exports-temds"
                To avoid Errors make sure this directory exists in gdrive before 
                running function
            'gcloud_cached_id': str, Optional
                id of cached directory in gdrive
            'local_cache': Path, Optional
                local cache of downloaded data        

        Returns
        -------
        TEMDataset or YearlyDataset
            subset of data from extent (`minx`,`miny`)(`maxx`,`maxy`)
            YearlyDataset is returned when `year` is not None

        """
        creds = kwargs['credentials']
        del(kwargs['credentials'])
        bounds = gpd.GeoDataFrame(
            {'geometry': shapely.box(minx, miny,  maxx, maxy)}, 
            index=['aoi'],
            crs=extent_crs
        ).bounds
        print(bounds)
        # return
        
        where = kwargs['download_location'] if 'download_location' in kwargs else "temp-gdrive-downloads"
        where = Path(where)
        where.mkdir(exist_ok=True, parents=True)

        if 'task_name' in kwargs:
            kwargs['name'] = kwargs['task_name']


        tile = self.download(
            where, 
            bounds, 
            creds, 
            **kwargs


            # name=name,
            # gdrive_location = gdrive_location,
            # gdrive_cached_id = cached_id,
            # local_cache=local_cache,
            
        )
        # return tile
        dataset = TEMDataset(tile)

        if self.year:
            dataset = YearlyDataset.from_TEMDataset(dataset, self.year)

        dataset=dataset.get_by_extent(minx, maxy, maxx, miny, extent_crs, **kwargs)

        return dataset 
    
    def __repr__(self):
        """string represnetation
        """
        return(f"{type(self).__module__}.{type(self).__name__}: {self.year}")

    def __lt__(self, other):
        """less than for sort
        """
        if self.year is None or other.year is None:
            raise errors.YearUnknownError(
                "An item in comparison is missing 'year' attribute"
            )
        return self.year < other.year
