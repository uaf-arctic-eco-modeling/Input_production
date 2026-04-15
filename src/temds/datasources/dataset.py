"""
dataset
-------

Objects to manage data for TEMDS project

"""
import os
from pathlib import Path
from copy import deepcopy
import operator
import gc
import pathlib
import shapely.geometry # for .box function

import xarray as xr
import numpy as np
import rioxarray  # activate 
import geopandas as gpd
import pandas as pd
import rasterio as rio
from osgeo import gdal
from affine import Affine
from pyproj import CRS
from cf_units import Unit
# from dapper.met import cmip_utils


import temds.datasources.vegetation
from . import errors
from . import worldclim, crujra, cmip6, topo
from . import soil_texture
from temds import file_tools
from temds import climate_variables 
from temds.logger import Logger
from temds.constants import MONTH_START_DAYS 
from temds.util import Version
from temds import gdal_tools


## We can better clear the memory cache on some OS's with this 
## trick. If libc.so.6 is not present the code dose nothing
try:
    import ctypes
    libc = ctypes.CDLL("libc.so.6") # clearing cache 
    malloc_trim = libc.malloc_trim
except:
    malloc_trim = lambda x: x ## do nothing 

gdal.UseExceptions()

class TEMDataset(object):
    """Class for managing .nc based data in TEMDS

    Attributes
    ----------
    _dataset: xr.dataset or Path
        should be accessed using the `dataset` property
        when `in_memory` is false this must be a Path
        otherwise it's a xr.dataset
    in_memory: Bool
        if True `_dataset` is an open xr.Dataset
        otherwise `_dataset is a Path to a .nc file
    logger: logger.Logger
        Logger to use for printing or saving messages
    _cached_load_kwargs: dict
        cached kwargs for loading `dataset` when `in_memory` is False

    Properties
    ----------
    dataset: xr.Dataset
        Provides access to internal `_dataset`, the getter
        will always provided access to an in memory version
        of the data. If `in_memory` is False the in memory 
        dataset is read only.
    crs: pyproj.CRS
        readonly access to `dataset` crs
    transform: affine.Affine
        readonly access to `dataset` geotransform
    resolution: Tuple
         readonly access to `dataset` resolution
    extent: Tuple
        readonly access to `dataset` extent
    vars: list
        readonly access to `dataset` data_vars
    units: dict
        access to a dictionary of variable names and units for 
        each variable in `vars`
    
    """
    def __init__(self, dataset, in_memory=True, logger=Logger(), **kwargs):
        """
        Parameters
        ----------
        dataset: xr.dataset or Path
            The dataset to load. When loaded the object should be able to 
            pass the `verify` function
        in_memory: Bool
            If True `dataset` is open as `xr.Dataset`.
            Otherwise it is stored as a Path.
        logger: logger.Logger, defaults to new object
            Logger to use for printing or saving messages
            The default Logger will not print any messages, but a 
            text file may be created from it by calling `logger.save`
        **kwargs:
            Key word arguments passed to `load` 
        """
        self._dataset = None
        self.logger = logger
        self.in_memory = in_memory
        self._cached_load_kwargs={}

        if isinstance(dataset, xr.Dataset):
            self.dataset=dataset
        else: # Path
            dataset = Path(dataset)
            if dataset.exists() and dataset.suffix == '.nc':
                
                if in_memory:
                    self.load(dataset, **kwargs)
                else:
                    self.dataset = dataset
                    self._cached_load_kwargs = kwargs

            else:
                raise IOError('input data is missing or not a .nc file')
        
    @property
    def crs(self):
        """Property for Quick access to crs"""
        return CRS(self.dataset.rio.crs)
    
    @property
    def shape(self):
        return self.dataset.rio.shape[::-1] # rio returns column major so swap
    
    @property
    def transform(self):
        """Property for Quick access to geo transform"""
        # print('transform')
        return self.dataset.rio.transform()

    @property
    def resolution(self):
        """Property for Quick access to resolution"""
        # print('res')
        return self.dataset.rio.resolution()
    
    @property
    def extent(self):
        """
        Returns (left,bottom,right,top), outer most coords (bounds) of the data.
        """
        return self.dataset.rio.bounds()

    @property
    def vars(self):
        """
        Property for quick access to variables in dataset
        """
        # print('vars')
        return [v for v in self.dataset.data_vars if v != 'spatial_ref']
    
    @property
    def units(self):
        """
        Property for quick access to units for variables in dataset
        """
        # print('units')
        return {var: Unit(self.dataset[var].units) for var in self.vars}
   
    @property
    def dataset(self):
        """This Property allow the objects data to be represented as a
        path in low memory systems instead of an open xr.Dataset.
        The file at the path can be open as needed.
        """
        if isinstance(self._dataset, xr.Dataset):
            return self._dataset
        elif isinstance(self._dataset, Path):
            return self.load(self._dataset, **self._cached_load_kwargs)
        else:
            raise TypeError('Bad Dataset Type')

    @dataset.setter
    def dataset(self, value):
        """Setting of dataset property."""
        self._dataset = value

    def __repr__(self):
        """string representation"""
        return(f"{type(self).__module__}.{type(self).__name__}")
    
    def __del__(self):
        """Explicitly close each dataset to hopefully avoid memory leaks"""
        # print('__del__')
        try:
            # if self.in_memory:
            self.dataset.close()
        except:
            pass

    @classmethod
    def from_region(cls, region, in_vars = [], ds_time_dim=[], buffer_px=0, logger=Logger() ):
        """
        Creates new xr.Dataset for `dataset` using the extent, transform, and 
        projection of `raster`. An optional buffer can be added to the extent
        when the crs is not ESPG:4326.

        Parameters
        ----------
        region: Region
            temds region
        in_vars: list, defaults []
            List of variables to create `Dataset.data_vars` for
        ds_time_dim: list, defaults []
            The time dimension for the `Dataset`
        buffer_px: int, default 0
            Buffer in pixels to add to extent. When `raster` crs is EPSG:4326
            This argument is ignored
        logger: logger.Logger, defaults to new object
            Logger to use for printing or saving messages
            The default Logger will not print any messages, but a 
            text file may be created from it by calling `logger.save`

        Returns
        -------
        TEMDataset
        """
        func_name = 'TEMdataset.from_region'
        logger.info(f'{func_name}: Initializing with extent from region: {region}')
        return cls.from_raster_extent(
            region.empty_gdal_dataset(), 
            in_vars, 
            ds_time_dim, 
            buffer_px, 
            logger
        )

    @classmethod
    def from_raster_extent(
            cls, raster, in_vars = [], ds_time_dim=[], buffer_px=0, logger=Logger()
        ):
        """
        Creates new xr.Dataset for `dataset` using the extent, transform, and 
        projection of `raster`. An optional buffer can be added to the extent
        when the crs is not ESPG:4326.

        Parameters
        ----------
        raster: Path
            Path to a raster file that can be opened as a gdal dataset
        in_vars: list, defaults []
            List of variables to create `Dataset.data_vars` for
        ds_time_dim: list, defaults []
            The time dimension for the `Dataset`
        buffer_px: int, default 0
            Buffer in pixels to add to extent. When `raster` crs is EPSG:4326
            This argument is ignored
        logger: logger.Logger, defaults to new object
            Logger to use for printing or saving messages
            The default Logger will not print any messages, but a 
            text file may be created from it by calling `logger.save`

        Returns
        -------
        TEMDataset
        """
        func_name = 'TEMdataset.from_raster_extent'
        logger.info(f'{func_name}: Initializing with extent from {raster}')
        if type(raster) is str or isinstance(raster, Path):
            # print('yo')
            extent_ds = gdal.Open(raster)
        else:
            extent_ds = raster

        ds_crs = CRS.from_wkt(extent_ds.GetProjection() )
        x_dim = 'x'
        y_dim = 'y'
        if ds_crs == CRS.from_epsg(4326): #is this true for other crs as well?
            logger.warn((
                f'{func_name}: When projection is wgs84(EPSG:4326) buffer_px '
                'is ignored'
            ))
            buffer_px = 0
            x_dim ='lon'
            y_dim = 'lat'

        ## TODO: if wgs84 we need some kind of check on bounds
            
        gt = extent_ds.GetGeoTransform()
        minx = gt[0] - (buffer_px * extent_ds.RasterXSize)
        maxy = gt[3] - (buffer_px * extent_ds.RasterYSize)
        maxx = minx + gt[1] * extent_ds.RasterXSize + (buffer_px * extent_ds.RasterXSize)
        miny = maxy + gt[5] * extent_ds.RasterYSize + (buffer_px * extent_ds.RasterYSize)
        
        extent = (minx, miny, maxx, maxy) #_warp_order
        logger.debug(f'{func_name}: extent {extent}')
        if buffer_px > 0:
            logger.info(f'{func_name}: extents includes buffer of {buffer_px} pixels')
        x_res, y_res = gt[1], gt[5]

        logger.debug(f'{func_name}: resolution, {x_res},{y_res}')
        logger.debug((
            f'{func_name}: out size {extent_ds.RasterXSize}, '
            f'{extent_ds.RasterYSize}'
        ))

        ## y_coords should almost alaways fall into the else category
        ## as most rasters are assumed to be top up
        if y_res > 0:
            # print('a') # should rarely be used
            y_array = np.arange(miny+y_res/2, maxy,  y_res)
        else: 
            # print('b')
            y_array = np.arange(miny-y_res/2, maxy,  abs(y_res))[::-1]
        
    
        x_array = np.arange(minx, maxx, abs(x_res)) + (abs(x_res)/2)
        rows, cols = len(y_array), len(x_array)

        # handle case where there are no time dimensions.
        n_time = len(ds_time_dim)

        if n_time > 0:
            dims = ['time', y_dim, x_dim]
            shape = [n_time, rows, cols]
            empty_data = np.zeros(n_time * rows * cols)\
                        .reshape(shape).astype('float32')
        else:
            dims = [y_dim, x_dim]
            shape = [rows, cols]
            empty_data = np.zeros(rows * cols)\
                        .reshape(shape).astype('float32')

        # TODO: drop the zero length time coord that gets created

        data_vars = { 
            var : (dims, deepcopy(empty_data) ) for var in in_vars
        }

        coords={
            y_dim: y_array, 
            x_dim: x_array,
        }
        if n_time > 0:
            coords['time'] = deepcopy(ds_time_dim)  
            ## the deep copy is to prevent shared memory issues
            ## might not be necessary here, but included just in case

        logger.info(f'{func_name}: output crs - {extent_ds.GetProjection()}')        

        ## change to x,y from lat,lon
        dataset = xr.Dataset(data_vars=data_vars, coords=coords)
        dataset.rio.write_crs(extent_ds.GetProjection(),inplace=True)\
            .rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim, inplace=True)\
            .rio.write_coordinate_system(inplace=True) 

        # from_gdal very important here.
        dataset.rio.write_transform(Affine.from_gdal(*gt), inplace=True)

        ## I don't know why but I have to do this twice. It's not the inplace
        ## not working and needing the assignment, I tried both ways in the 
        ## first call above and it didn't make a difference. 
        dataset = dataset\
            .rio.write_crs(dataset.rio.crs.to_wkt(), inplace=True)\
            .rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim , inplace=True)\
            .rio.write_coordinate_system(inplace=True)

        return TEMDataset(dataset, logger=logger)

    @staticmethod
    def from_soil_texture(data_path, extent_raster=None, download=False,
                          overwrite=False, logger=Logger(), buffer=0,
                          resample_alg='average'):
        func_name = "TEMdataset.from_soil_texture"
        logger.info(f'{func_name}: Processing soil texture data in {data_path}')

        if download:
            logger.info(f'{func_name}: Downloading data.')
            file_tools.download_all_files(soil_texture.urlsand, data_path, overwrite)
            file_tools.download_all_files(soil_texture.urlsilt, data_path, overwrite)
            file_tools.download_all_files(soil_texture.urlclay, data_path, overwrite)

        # ???if not Path(data_path, soil_texture..

        if not extent_raster:
            raise ValueError(f'{func_name}: extent_raster is required!')

        logger.info(f'{func_name}: Using extent from {extent_raster}')
        er = gdal.Open(extent_raster)

        # Original method seemed to have some extra steps...
        # also the original method didn't seem to process the sand file??
        # starts at 1km in some strange projection
        # crop to just high latitude
        # average across depths
        # reproject to 6931 and put at 4km rez
        # resample to 50km rez
        # resample to 4km rez
        # run thru extra python script : 
        #   where the fine rez file is -9999, 
        #   take the coarse value, 
        #   otherwise take the fine value.

        # Get the extent from the extent raster
        er_gt = er.GetGeoTransform()
        er_minx = er_gt[0]
        er_miny = er_gt[3]
        er_maxx = er_gt[0] + (er_gt[1] * er.RasterXSize)  
        er_maxy = er_gt[3] + (er_gt[5] * er.RasterYSize)

        logger.info(f'{func_name}: Creating empty xarray dataset')
        newDS = TEMDataset.from_raster_extent(extent_raster, 
                                              in_vars='pct_clay pct_sand pct_silt'.split(), 
                                              ds_time_dim=[], buffer_px=0)

        for X in ['clay','sand','silt']:
            logger.info(f'{func_name}: Processing {X} data')

            ds_15_30 = gdal.Open(pathlib.Path(data_path, f'{X}_15-30cm_mean_1000.tif'))
            ds_30_60 = gdal.Open(pathlib.Path(data_path, f'{X}_30-60cm_mean_1000.tif'))
            ds_60_100 = gdal.Open(pathlib.Path(data_path, f'{X}_60-100cm_mean_1000.tif'))

            assert ds_15_30.GetSpatialRef().IsSame(ds_30_60.GetSpatialRef()), "CRS mismatch"
            assert ds_15_30.GetSpatialRef().IsSame(ds_60_100.GetSpatialRef()), "CRS mismatch"

            warpOpts = gdal.WarpOptions(
                        format='MEM',
                        srcSRS=ds_15_30.GetSpatialRef(), 
                        dstSRS=er.GetSpatialRef(), 
                        xRes=er.GetGeoTransform()[1], 
                        yRes=er.GetGeoTransform()[5], 
                        resampleAlg='average', 
                        outputType=gdal.GDT_Float32, 
                        outputBounds=[er_minx, er_miny, er_maxx, er_maxy])

            # crop them all down to the AOI
            dst_1530 = gdal.Warp("", ds_15_30, options=warpOpts)
            dst_3060 = gdal.Warp("", ds_30_60, options=warpOpts)
            dst_60100 = gdal.Warp("", ds_60_100, options=warpOpts)

            # Find the average over the 3 depth ranges
            avg = (dst_1530.ReadAsArray() * 15 + dst_3060.ReadAsArray() * 30 + dst_60100.ReadAsArray() * 40) / (150 + 300 + 400)


            logger.info(f'{func_name}: Assigning data to the new dataset')
            newDS.dataset[f'pct_{X}'] = (['y','x'], avg)

        newDS.dataset['pct_clay'].attrs.update(units='percent')
        newDS.dataset['pct_sand'].attrs.update(units='percent')
        newDS.dataset['pct_silt'].attrs.update(units='percent')
        newDS.dataset.rio.set_spatial_dims(x_dim="x", y_dim="y", inplace=True)\
                    .rio.write_crs(er.GetProjection(), inplace=True)\
                    .rio.write_coordinate_system(inplace=True) 

        return newDS

    @classmethod
    def from_vegetation(
            cls,
            land_cover_raster: Path,
            land_cover_classes: Path,
            global_political_map: Path, 
            eco_region_map: Path,
            region, 
            download=False,
            overwrite=False, logger=Logger(), buffer=0
        ):
        func_name = "TEMdataset.from_vegetation"

        logger.info(f'{func_name}: Processing vegetation data from: ')
        logger.info(f'               {land_cover_raster}')
        logger.info(f'               {land_cover_classes}')
        logger.info(f'               {global_political_map}')
        logger.info(f'               {eco_region_map}')


        if download:
            raise NotImplementedError('Vegetation download not implemented yet!')

        logger.info(f'{func_name}: Reading shapefiles')

        political_shp = gpd.read_file(global_political_map)
        eco_shp = gpd.read_file(eco_region_map)
        #clip to broad area in 4326 then clip to exact area in region.crs
        political_shp = political_shp.clip(region.get_extent('4326', True)).to_crs(region.crs).clip(region.get_extent())
        eco_shp = eco_shp.clip(region.get_extent('4326', True)).to_crs(region.crs).clip(region.get_extent())
        

        logger.info(f'{func_name}: Processing political shapefile')

        def get_gdf(shape_obj, key = 'shapeName', idx_name = 'state_idx'):
            '''Opens a shapefile, creates in index based on the unique values found
            in the specified key column. Adds this index to a data frame. Make the
             index 1 based. Then turn it into a geodataframe and return it.'''
            f2 = func_name + ".get_gdf"
            logger.debug(f"{f2}: Creating index ({idx_name}) for {key} in shape object..")
            if key not in shape_obj.columns:
                raise ValueError(f'Key {key} not found in shapefile columns')
            df = pd.DataFrame(shape_obj[key].unique())
            df.reset_index(inplace=True)
            df = df.set_axis([idx_name,key], axis=1)
            df[idx_name] += 1 # make it 1 based
            df_f  = shape_obj.merge(df, on=key, how='left')
            geo_df = gpd.GeoDataFrame(df_f)

            return geo_df

        country_geo_df = get_gdf(political_shp,  'shapeGroup', 'ctry_idx',)
        state_geo_df = get_gdf(political_shp,  'shapeName', 'state_idx',)
        eco_geo_df = get_gdf(eco_shp,  'ECO_NAME', 'eco_idx',)
        biome_geo_df = get_gdf(eco_shp,  'BIOME_NAME', 'biome_idx',)
        ecobiome_geo_df = get_gdf(eco_shp,  'ECO_BIOME_', 'ecobiome_idx',)
        realm_geo_df = get_gdf(eco_shp,  'REALM', 'realm_idx',)

        def burn_gdf(raster_fpath, gdf, idx_col, meta):
            f2 = func_name + ".burn_gdf"
            with rio.open(raster_fpath, 'w+', **meta) as out:
                out_arr = out.read(1)
                shapes = ((geom,value) for geom, value in zip(gdf.geometry, gdf[idx_col]))
                burned = rio.features.rasterize(shapes=shapes, fill=-9999, out=out_arr, transform=out.transform)
                logger.info(f'{f2}: Writing {raster_fpath}')
                out.write_band(1, burned)

        files = [
            '/tmp/country_raster_temp_from_veg.tif',
            '/tmp/state_raster_temp_from_veg.tif',
            '/tmp/eco_raster_temp_from_veg.tif',
            '/tmp/biome_raster_temp_from_veg.tif',
            '/tmp/ecobiome_raster_temp_from_veg.tif',
            '/tmp/realm_raster_temp_from_veg.tif',
            '/tmp/TEM_Landcover_V4_temp_from_veg.tif',
            '/tmp/drainage_raster_temp_from_veg.tif',
        ]
        [os.unlink(f) for f in files if os.path.exists(f)]

        # meta = ER.meta.copy()
        meta = {
            'driver': 'GTiff',
            'dtype': 'float32',
            'nodata': None,
            'width': region.shape[0],
            'height': region.shape[1],
            'count': 1,
            'crs': region.crs,
            'transform': Affine.from_gdal(*region.transform),
            'compress': 'lzw'
        }

        # meta.update(compress='lzw')
        burn_gdf('/tmp/country_raster_temp_from_veg.tif', country_geo_df, 'ctry_idx', meta)
        burn_gdf('/tmp/state_raster_temp_from_veg.tif', state_geo_df, 'state_idx', meta)
        burn_gdf('/tmp/eco_raster_temp_from_veg.tif', eco_geo_df, 'eco_idx', meta)
        burn_gdf('/tmp/biome_raster_temp_from_veg.tif', biome_geo_df, 'biome_idx', meta)
        burn_gdf('/tmp/ecobiome_raster_temp_from_veg.tif', ecobiome_geo_df, 'ecobiome_idx', meta)
        burn_gdf('/tmp/realm_raster_temp_from_veg.tif', realm_geo_df, 'realm_idx', meta)

        extent_raster = region.empty_gdal_dataset()
        logger.info(f"{func_name}: Convert the TEM_Landcover_V4 to match the  AOI raster in extents and resolution")
        gdal.Warp(
            extent_raster,
            land_cover_raster,
            options=gdal.WarpOptions(
                resampleAlg='mode',
            ))
        extent_raster.FlushCache()
        driver = gdal.GetDriverByName('GTiff')
        driver.CreateCopy("/tmp/TEM_Landcover_V4_temp_from_veg.tif",extent_raster)
        del(driver)

       
        if 'topo' in region.data:
            topo = region.data['topo']
        else:
            raise NotImplementedError('Need to add back options to load topo for raw/or other preprocessed data')
            # # slow.... for large areas
            # topo = TEMDataset.from_topo(
            #     'working/00-download/topo/',
            #     extent_raster,
            #     download=False,
            #     logger=logger,
            # )

        # Make sure we only write out the variable we are interested in.
        topo.dataset['drainage_class'].astype(np.int32).rio.to_raster("/tmp/drainage_raster_temp_from_veg.tif")

        index_names = ['ctry_idx', 'state_idx', 'eco_idx', 'biome_idx', 'ecobiome_idx', 'realm_idx', 'lc_idx', 'drain_idx']
        
        def generate_indices(files, index_names):
            # Reads in each raster, flattens it and creates a data frame 
            # with an index set on the dataframe...
            f2 = func_name + "generate_indices"
            for f, idx_name in zip(files, index_names):
                with rio.open(f) as src:
                    logger.debug(f"{f2} reading {f} with shape {src.shape}")
                    arr = src.read(1)
                    df = pd.DataFrame(arr.flatten())
                    df = df.set_axis([idx_name], axis=1)
                    yield df
        
        # This is a table with one row per pixel and columns for each index.
        logger.info(f"{func_name}: Creating the ecotype table by concatening all the indices...")
        ecotype = pd.concat(list(generate_indices(files, index_names)), axis=1)
        
        logger.info(f"{func_name}: Loading the land cover classification...")
        classif = pd.read_csv(land_cover_classes)
        classif = classif.rename(columns={"value": "lc_idx"})
        classif = classif.rename(columns={"classname ": "classname"}) # there is a trailing space in the csv column name

        
        ecotype['classname'] = 'N/A'
        for row in classif.T: 
            lc_idx = classif.loc[row,'lc_idx']
            cn = classif.loc[row,'classname']
            idx = (ecotype['lc_idx'] == lc_idx)
            ecotype.loc[idx, 'classname'] = cn


        # Put back in the text based lables for country and state (shapeName and shapeGroup)
        ecotype = pd.merge(ecotype, state_geo_df.drop(['geometry', 'shapeType', 'shapeID'], axis=1), on=['state_idx'], how='left')

        # put back in the text based labels for biome, realm, etc
        ecotype = pd.merge(ecotype, eco_geo_df.drop(['OBJECTID','BIOME_NUM','ECO_BIOME_','NNH','ECO_ID','SHAPE_LENG','SHAPE_AREA','NNH_NAME','COLOR', 'COLOR_BIO', 'COLOR_NNH', 'LICENSE', 'geometry',], axis=1), on=['eco_idx'], how='left')

        # Add subregion column
        ecotype['subregion'] = "N/A"

        idx = ( (ecotype['shapeName'] == 'Alaska') | \
                    (ecotype['ECO_NAME'] == 'Pacific Coastal Mountain icefields and tundra') | \
                    (ecotype['ECO_NAME'] == 'Alaska-St. Elias Range tundra') | \
                    (ecotype['ECO_NAME'] == 'Interior Yukon-Alaska alpine tundra') | \
                    (ecotype['ECO_NAME'] == 'Brooks-British Range tundra') | \
                    (ecotype['ECO_NAME'] == 'Arctic foothills tundra') | \
                    (ecotype['ECO_NAME'] == 'Interior Yukon-Alaska alpine tundra') )
        ecotype['subregion'] = np.where(idx, 'Western North America', ecotype['subregion'])

        idx = ( (ecotype['shapeGroup'] == 'CAN') & (ecotype['ECO_NAME'] == 'Ogilvie-MacKenzie alpine tundra') )
        ecotype['subregion'] = np.where(idx, 'Central North America', ecotype['subregion'])

        idx = ( ((ecotype['shapeGroup'] == 'CAN') | (ecotype['shapeGroup'] == 'GRL')) & \
                    (ecotype['shapeName'] == 'Quebec') |  \
                    (ecotype['shapeName'] == 'Ontario') | \
                    (ecotype['shapeName'] == 'Newfoundland and Labrador') | \
                    (ecotype['ECO_NAME'] == 'Southern Hudson Bay taiga') | \
                    (ecotype['ECO_NAME'] == 'Central Canadian Shield forests') | \
                    (ecotype['ECO_NAME'] == 'Eastern Canadian Forest-Boreal transition') )
        ecotype['subregion'] = np.where(idx, 'Eastern North America', ecotype['subregion'])


        idx = ( (ecotype['shapeGroup'] == 'RUS') )
        ecotype['subregion'] = np.where(idx, 'Eastern Eurasia', ecotype['subregion'])

        idx = ( (ecotype['ECO_NAME'] == 'Yamal-Gydan tundra') | \
                   (ecotype['ECO_NAME'] == 'Russian Arctic desert') | \
                   (ecotype['ECO_NAME'] == 'West Siberian taiga') | \
                   (ecotype['ECO_NAME'] == 'Western Siberian hemiboreal forests') | \
                   (ecotype['ECO_NAME'] == 'South Siberian forest steppe') | \
                   (ecotype['ECO_NAME'] == 'Northwest Russian-Novaya Zemlya tundra') | \
                   (ecotype['ECO_NAME'] == 'Trans-Baikal conifer forests') | \
                   (ecotype['ECO_NAME'] == 'Kazakh forest steppe') ) 
        ecotype['subregion'] = np.where(idx, 'Central Eurasia', ecotype['subregion'])

        idx = ( (ecotype['shapeGroup'] == 'NOR') | \
                   (ecotype['shapeGroup'] == 'SWE') | \
                   (ecotype['shapeGroup'] == 'FIN') | \
                   (ecotype['shapeGroup'] == 'ISL') | \
                   (ecotype['ECO_NAME'] == 'Kola Peninsula tundra') | \
                   (ecotype['ECO_NAME'] == 'Scandinavian and Russian taiga') | \
                   (ecotype['ECO_NAME'] == 'Temperate Broadleaf & Mixed Forests') | \
                   (ecotype['ECO_NAME'] == 'Urals montane forest and taiga') )
        ecotype['subregion'] = np.where(idx, 'Western Eurasia', ecotype['subregion']) 

        # Add an alpine column
        ecotype['alpine'] = 'N/A'
        alpine_idx = ( ecotype['ECO_NAME'].str.contains('alpine', case=False) | \
                       ecotype['ECO_NAME'].str.contains('montane', case=False) | \
                       ecotype['ECO_NAME'].str.contains('mountain', case=False) | \
                       ecotype['ECO_NAME'].str.contains('mountains', case=False) | \
                       ecotype['ECO_NAME'].str.contains('range', case=False) | \
                       ecotype['ECO_NAME'].str.contains('rockies', case=False) | \
                       ecotype['ECO_NAME'].str.contains('cordillera', case=False) | \
                       ecotype['ECO_NAME'].str.contains('rock', case=False) )
        ecotype['alpine'] = np.where(alpine_idx, 1, 0)

        # add a community column
        ecotype['community '] = 'N/A'

        idx = ( (ecotype['classname'] == 'White Spruce forest') )
        ecotype['community'] = np.where(idx, 'white spruce forest', ecotype['community '])

        idx = ( (ecotype['classname'] == 'Black Spruce forest') | \
                (ecotype['classname'] == 'Spruce forest') | \
                (ecotype['classname'] == 'Fir forest') | \
                (ecotype['classname'] == 'Hemlock forest') )
        ecotype['community'] = np.where(idx, 'black spruce forest', ecotype['community'])

        idx = ( (ecotype['classname'] == 'Aspen forest') )
        ecotype['community'] = np.where(idx, 'aspen forest', ecotype['community'])

        idx = ( (ecotype['classname'] == 'Birch forest') | \
                (ecotype['classname'] == 'Poplar forest') | \
                (ecotype['classname'] == 'Maple') | \
                (ecotype['classname'] == 'Oak forest') | \
                (ecotype['classname'] == 'Linden') )
        ecotype['community'] = np.where(idx, 'birch forest', ecotype['community'])

        idx = ( (ecotype['classname'] == 'Mixed forest') )
        ecotype['community'] = np.where(idx, 'mixed forest', ecotype['community'])

        idx = ( (ecotype['classname'] == 'Larch forest') )
        ecotype['community'] = np.where(idx, 'larch forest', ecotype['community'])

        idx = ( (ecotype['classname'] == 'Scotts Pine forest') | \
                (ecotype['classname'] == 'Siberian Pine') )
        ecotype['community'] = np.where(idx, 'scots pine forest', ecotype['community'])

        idx = ( (ecotype['classname'] == 'Jack Pine forest') | \
                (ecotype['classname'] == 'Pine forest') )
        ecotype['community'] = np.where(idx, 'jack pine forest', ecotype['community'])

        idx = ( (ecotype['classname'] == 'Pine forest') & (ecotype['REALM'] == 'Palearctic') )
        ecotype['community'] = np.where(idx, 'scots pine forest', ecotype['community'])

        idx = ( (ecotype['classname'] == 'Herbaceous') | \
                (ecotype['classname'] == 'Graminoid tundra') )
        ecotype['community'] = np.where(idx, 'tussock tundra', ecotype['community'])

        idx = ( (ecotype['classname'] == 'Other shrublands') | \
                (ecotype['classname'] == 'Cedar Elfin Wood') | \
                (ecotype['classname'] == 'Erect-shrub tundra') | \
                (ecotype['classname'] == 'Shrub tundra') | \
                (ecotype['classname'] == 'Alpine shrubland') | \
                (ecotype['classname'] == 'Prostrate-shrub tundra') | \
                (ecotype['classname'] == 'Riparian shrubland') )
        ecotype['community'] = np.where(idx, 'shrub tundra', ecotype['community'])

        idx = ( (ecotype['classname'] == 'Barren tundra') | \
                (ecotype['classname'] == 'Sparsely Vegetated') )
        ecotype['community'] = np.where(idx, 'heath tundra', ecotype['community'])

        idx = ( (ecotype['classname'] == 'Fen') )
        ecotype['community'] = np.where(idx, 'fen', ecotype['community'])

        idx = ( (ecotype['classname'] == 'Bog') )
        ecotype['community'] = np.where(idx, 'bog', ecotype['community'])
        
        idx = ( (ecotype['classname'] == 'Wet-sedge tundra') | \
                (ecotype['classname'] == 'Marsh') )
        ecotype['community'] = np.where(idx, 'wetsedge tundra', ecotype['community'])

        ecotype['CMT'] = 'CMT00'
        ecotype['CMT'] = np.where((ecotype['community'] == 'black spruce forest'),'CMT01',ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'white spruce forest'),'CMT02',ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'jack pine forest'),'CMT66',ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'scots pine forest'),'CMT74',ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'larch forest'),'CMT71',ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'mixed forest'),'CMT67',ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'birch forest'),'CMT03',ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'aspen forest'),'CMT65',ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'shrub tundra'),'CMT04',ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'tussock tundra'),'CMT05',ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'heath tundra'),'CMT07',ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'wetsedge tundra'),'CMT06',ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'bog'),'CMT31',ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'fen'),'CMT55',ecotype['CMT'])

        # drain_idx: 1 --> poorly drained, 0 --> well drained
        ecotype['CMT'] = np.where((ecotype['community'] == 'black spruce forest') & (ecotype['subregion'] == 'Western North America') & (ecotype['drain_idx'] == 1), 'CMT13', ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'black spruce forest') & ((ecotype['subregion'] == 'Central North America') | (ecotype['subregion'] == 'Eastern North America')) & (ecotype['drain_idx'] == 1), 'CMT60', ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'black spruce forest') & ((ecotype['subregion'] == 'Central North America') | (ecotype['subregion'] == 'Eastern North America')) & (ecotype['drain_idx'] == 0), 'CMT69', ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'bog') & ((ecotype['subregion'] == 'Central North America') | (ecotype['subregion'] == 'Eastern North America')), 'CMT61', ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'bog') & ((ecotype['subregion'] == 'Eastern Eurasia') | (ecotype['subregion'] == 'Central Eurasia')), 'CMT75', ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'bog') & (ecotype['subregion'] == 'Western Eurasia'), 'CMT80', ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'bog') & ((ecotype['ECO_NAME'] == 'Russian Arctic desert') | (ecotype['ECO_NAME'] == 'Kola Peninsula tundra') | (ecotype['ECO_NAME'] == 'Scandinavian coastal conifer forests') | (ecotype['ECO_NAME'] == 'Scandinavian Montane Birch forest and grasslands')) , 'CMT92', ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'fen') & (ecotype['REALM'] == 'Palearctic') , 'CMT91', ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'heath tundra') & (ecotype['subregion'] == 'Central North America'), 'CMT52', ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'heath tundra') & (ecotype['subregion'] == 'Eastern North America'), 'CMT90', ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'heath tundra') & (ecotype['REALM'] == 'Palearctic'), 'CMT90', ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'larch forest') & ((ecotype['subregion'] == 'Central Eurasia') | (ecotype['subregion'] == 'Western Eurasia')),'CMT72',ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'mixed forest') & (ecotype['REALM'] == 'Palearctic'),'CMT77',ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'scots pine forest') & (ecotype['subregion'] == 'Western Eurasia'),'CMT82',ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'shrub tundra') & ((ecotype['subregion'] == 'Central North America') | (ecotype['subregion'] == 'Eastern North America')), 'CMT50', ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'shrub tundra') & (ecotype['subregion'] == 'Eastern Eurasia'), 'CMT70', ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'shrub tundra') & ((ecotype['subregion'] == 'Western Eurasia') | (ecotype['subregion'] == 'Central Eurasia')), 'CMT76', ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'shrub tundra') & (ecotype['alpine'] == 'alpine'),'CMT20',ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'tussock tundra') & ((ecotype['subregion'] == 'Central North America') | (ecotype['subregion'] == 'Eastern North America')), 'CMT51', ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'tussock tundra') & (ecotype['REALM'] == 'Palearctic'), 'CMT73', ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'tussock tundra') & (ecotype['alpine'] == 'alpine'),'CMT21',ecotype['CMT'])
        ecotype['CMT'] = np.where((ecotype['community'] == 'wetsedge tundra') & (ecotype['REALM'] == 'Palearctic'), 'CMT77', ecotype['CMT'])

        ecotype['CMT_num'] = pd.to_numeric(ecotype['CMT'].str.extract('(\d+)', expand=False)).fillna(np.int32(-9999)).astype(np.int32)

        logger.info(f'{func_name}: Creating empty xarray dataset')
        newDS = TEMDataset.from_region(region, 
                                              in_vars=['veg_class'], 
                                              ds_time_dim=[], buffer_px=0)


        # dunno why, but this data comes out flipped, so we reverse the y axis here
        logger.info(f'{func_name}: Assigning data to the new dataset')
        newDS.dataset['veg_class'] = (
            ['y','x'], ( 
                np.reshape(
                    ecotype['CMT_num'], (region.shape[1],region.shape[0])
                ).astype(float) # need to figure out issue with saving int data
            )
        )


        newDS.dataset['veg_class'].attrs.update(units='', name='Community Type Classification')
        
        newDS.dataset.rio.set_spatial_dims(x_dim="x", y_dim="y", inplace=True)\
                    .rio.write_crs(region.crs.to_wkt(), inplace=True)\
                    .rio.write_coordinate_system(inplace=True) 


        return newDS


    @staticmethod
    def from_historic_explicit_fire(synthetic=True, extent_raster_path=None, synthetic_time=None, logger=Logger()):
        func_name = "TEMdataset.from_historic_explicit_fire"
        logger.info(f'{func_name}: Processing explicit fire data')   

        if extent_raster_path is None:
            raise ValueError(f'{func_name}: extent_raster_path is required!')
        
        logger.info(f'{func_name}: Using extent from {extent_raster_path}')
        extent_raster = gdal.Open(extent_raster_path)

        logger.info(f'{func_name}: Creating empty xarray dataset...')
        newDS = TEMDataset.from_raster_extent(extent_raster_path, 
                                      in_vars=['exp_burn_mask','exp_fire_severity','exp_jday_of_burn','exp_area_of_burn',],
                                      ds_time_dim=[], buffer_px=0)
        # if not isinstance(synthetic_time, xr.DataArray):
        #     raise ValueError(f'{func_name}: synthetic_time must be an xarray DataArray!')   

        if isinstance(synthetic, xr.DataArray):
            logger.info(f'{func_name}: Generating synthetic data arrays...')
            time_length = synthetic.sizes['time']
            exp_burn_mask = np.zeros(shape=(time_length, extent_raster.RasterYSize, extent_raster.RasterXSize))
            exp_fire_severity = np.zeros(shape=(time_length, extent_raster.RasterYSize, extent_raster.RasterXSize))
            exp_jday_of_burn = np.zeros(shape=(time_length, extent_raster.RasterYSize, extent_raster.RasterXSize))
            exp_area_of_burn = np.zeros(shape=(time_length, extent_raster.RasterYSize, extent_raster.RasterXSize))
        else:
            raise NotImplementedError(f'{func_name}: Non-synthetic data not yet implemented!')

        logger.info(f'{func_name}: Assigning data to the new dataset')
        newDS.dataset['exp_burn_mask'] = (['time','y','x'], exp_burn_mask)
        newDS.dataset['exp_fire_severity'] = (['time','y','x'], exp_fire_severity)
        newDS.dataset['exp_jday_of_burn'] = (['time','y','x'], exp_jday_of_burn)
        newDS.dataset['exp_area_of_burn'] = (['time','y','x'], exp_area_of_burn)

        logger.info(f'{func_name}: Setting attributes for data variables')
        newDS.dataset['exp_burn_mask'].attrs.update(units='', name='Fire Occurrence')
        newDS.dataset['exp_fire_severity'].attrs.update(units='', name='Fire Severity')
        newDS.dataset['exp_jday_of_burn'].attrs.update(units='', name='Julian Day of Burn')
        newDS.dataset['exp_area_of_burn'].attrs.update(units='km-2', name='Area of Burn (km-2)')

        return newDS

    @staticmethod
    def from_fri(synthetic=True, extent_raster_path=None, logger=Logger()):
        func_name = "TEMdataset.from_fri"
        logger.info(f'{func_name}: Processing fire return interval data')   

        if extent_raster_path is None:
            raise ValueError(f'{func_name}: extent_raster_path is required!')
        
        logger.info(f'{func_name}: Using extent from {extent_raster_path}')
        extent_raster = gdal.Open(extent_raster_path)

        logger.info(f'{func_name}: Creating empty xarray dataset...')
        newDS = TEMDataset.from_raster_extent(extent_raster_path, 
                                      in_vars=['fri','fri_severity','fri_jday_of_burn','fri_area_of_burn',],
                                      ds_time_dim=[], buffer_px=0)

        if synthetic:
            logger.info(f'{func_name}: Generating synthetic data arrays...')
            fri = np.ones(shape=(extent_raster.RasterYSize, extent_raster.RasterXSize))*2000
            fri_severity = np.ones(shape=(extent_raster.RasterYSize, extent_raster.RasterXSize))*2
            fri_jday_of_burn = np.ones(shape=(extent_raster.RasterYSize, extent_raster.RasterXSize))+160
            fri_area_of_burn = np.ones(shape=(extent_raster.RasterYSize, extent_raster.RasterXSize))*1
        else:
            raise NotImplementedError(f'{func_name}: Non-synthetic data not yet implemented!')


        logger.info(f'{func_name}: Assigning data to the new dataset')
        newDS.dataset['fri'] = (['y','x'], fri)
        newDS.dataset['fri_severity'] = (['y','x'], fri_severity)
        newDS.dataset['fri_jday_of_burn'] = (['y','x'], fri_jday_of_burn)
        newDS.dataset['fri_area_of_burn'] = (['y','x'], fri_area_of_burn)

        logger.info(f'{func_name}: Setting attributes for data variables')
        newDS.dataset['fri'].attrs.update(units='', name='Fire Return Interval')
        newDS.dataset['fri_severity'].attrs.update(units='', name='Fire Severity')
        newDS.dataset['fri_jday_of_burn'].attrs.update(units='', name='Julian Day of Burn')
        newDS.dataset['fri_area_of_burn'].attrs.update(units='', name='Area of Burn (km2)')

        logger.info(f'{func_name}: Setting spatial properties for dataset from {extent_raster_path}')
        newDS.dataset.rio.set_spatial_dims(x_dim="x", y_dim="y", inplace=True)\
                    .rio.write_crs(extent_raster.GetProjection(), inplace=True)\
                    .rio.write_coordinate_system(inplace=True) 


        return newDS
    


    @classmethod
    def from_topo(
            cls, data_path, region, download=False, url=topo.URL,
            overwrite=False, resample_alg='average', logger=Logger(),
        ):
        """Create dataset from raw topo data. TODO: document spesifics

        Parameters
        ----------
        data_path: Path
            Path to topo data (see TODO above)
        region: region.Region
            Extent dataset
        download: bool, default False
            Data is downloaded when true. If data exists overwrite must also
            be Ture
        overwrite: bool, default False
            Flags if data can be overwritten
        resample_alg: str, defaults, average
            Algoritm for resampling elevation from source data
        logger.Logger, defaults to new object
            Logger to use for printing or saving messages
            The default Logger will not print any messages, but a 
            text file may be created from it by calling `logger.save

        Returns
        -------
        TEMDataset
        """
        func_name = "TEMdataset.from_topo"
        logger.info(f'{func_name}: Processing topography data in {data_path}')

        if download:
            logger.info(f'{func_name}: Downloading data.')
            data_path = file_tools.download(url, data_path, overwrite)

        if data_path.suffix == '.zip':
            logger.info(f'{func_name}: Extracting data to {data_path.parent}.')
            data_path = file_tools.extract(data_path, data_path.parent)/data_path.stem 

        logger.info(f'{func_name}: Loading topography data.')
        full_data = gdal.Open(data_path)

        logger.info(f'{func_name}: Computing target area elevation (gdal.warp)')
        elevation = topo.create_elevation(full_data, region, resample_alg)
        logger.info(f'{func_name}: Computing aspect, slope, and TPI.')
        slope = topo.create_slope(elevation)
        aspect = topo.create_aspect(elevation)
        tpi = topo.create_tpi(elevation)
        logger.info(f'{func_name}: Computing Drainage Class.')
        drainage_class = topo.create_drainage_class(slope)

        newDS = cls.from_region(
            region, 
            in_vars=['elevation','aspect','slope','TPI','drainage_class'],
            ds_time_dim=[], 
            buffer_px=0
        )

        logger.info(f'{func_name}: Assigning data to the new dataset')
        newDS.dataset['elevation'] = (['y','x'], elevation.ReadAsArray().astype(float))
        newDS.dataset['aspect'] = (['y','x'], aspect.ReadAsArray().astype(float))
        newDS.dataset['slope'] = (['y','x'], slope.ReadAsArray().astype(float))
        newDS.dataset['TPI'] = (['y','x'], tpi.ReadAsArray().astype(float))
        newDS.dataset['drainage_class'] = (['y','x'], drainage_class.astype(float))

        newDS.dataset['elevation'].attrs.update(units='m', name='Elevation')
        newDS.dataset['aspect'].attrs.update(units='degrees', name='Aspect')
        newDS.dataset['slope'].attrs.update(units='degrees', name='Slope')
        newDS.dataset['TPI'].attrs.update(units='', name='Topographic Position Index')
        newDS.dataset['drainage_class'].attrs.update(units='', name='Drainage Class (1=poorly drained, 0=well drained)')

        newDS.dataset.rio.set_spatial_dims(x_dim="x", y_dim="y", inplace=True)\
                    .rio.write_crs(elevation.GetProjection(), inplace=True)\
                    .rio.write_coordinate_system(inplace=True) 

        return newDS

    @classmethod
    def from_worldclim(
            cls,
            data_path, 
            region = None,
            download=False, 
            version='2.1', 
            resolution='30s', 
            in_vars='all', 
            # extent_raster=None,
            overwrite=False, 
            logger=Logger(),
            resample_alg='bilinear'
        ):
        """Creates a TEMDataset that will pass `verify` from source Worldclim
        data. Can be used to download data or create from local data. Uses
        GDAL.Warp to convert data  to extent, crs, and resolution 
        from `extent_raster`

        Parameters
        ----------
        data_path: path
            Path to source data location on local machine. If download is True
            the data is downloaded to this location first. 
        region: Region
            region to get data for
        download: Bool, default False
            If True, data is downloaded using urls generated with 
            `worldclim.url_for` 
        version: str, defaults '2.1' 
            Worldclim data release.
        resolution: str, defaults '30s'
            Worldclim spatial resolution. Must be in `worldclim.RESOLUTIONS`
        in_vars: list or str defaults 'all'
            Variables to create `TEMDataset` from.
            If a str, should be a single var name, or `all` which will
            use all variables `worldclim.vars` 
            If a list, a list of variables in `worldclim.vars` 
        overwrite: bool, defaults False 
            If true, overwrite existing data.
        logger: logger.Logger, defaults to new object
            Logger to use for printing or saving messages
            The default Logger will not print any messages, but a 
            text file may be created from it by calling `logger.save`
        resample_alg: str, defaults 'bilinear'
            Resampling algorithm for converting source data to 
            extent, crs, and resolution from `extent_raster`

        Returns
        -------
        TEMDataset
            A TEM dataset that will pass `verify`
        """
        ## used in messages.
        func_name = "TEMdataset.from_worldclim"
        if in_vars == 'all':
            in_vars = worldclim.VARS
        if type(in_vars) is not list:
            in_vars = [in_vars]
        completed = {}
        logger.info(f'{func_name}: Processing Worldclim data in {data_path}')

        ## download first if needed
        if download: # get from web
            worldclim.download(data_path, in_vars, version, resolution, overwrite, logger)


        #get available data, unzip if needed
        completed = worldclim.prepare(data_path, in_vars, version, resolution, overwrite, logger)

        logger.debug(
            f'{func_name}: Initializing with extent from region'
        )
        
        new = TEMDataset.from_region(
            region, 
            in_vars=in_vars, 
            ds_time_dim=MONTH_START_DAYS, 
            logger=logger,
            buffer_px=0
        )
        # new the TEMDataset object does not seem to be geo-refd at this point...
        # but new.dataset is geo-refed...and it looks like the right spot too.
        logger.info(f"{func_name}: Initialization complete")
        logger.info(f"{func_name}: {new.dataset.rio.transform()=}")
        logger.info(f"{func_name}: {new.dataset.rio.transform().to_gdal()=}")
        logger.info(
            f'{func_name}: Running gdal.Warp to extent {region.get_extent()} on all data'
        )

        result = region.empty_gdal_dataset()
        for var in in_vars:
            cv = climate_variables.lookup_alias(worldclim.NAME, var)
            unit = cv.std_unit.name
            v_name = cv.name

            ## this is inplace as opposed to assign_attrs
            new.dataset[var].attrs.update(units=unit, name=v_name)

            in_dir = completed[var]
            for month in range(1,13):
                idx = month-1
                name = worldclim.name_for(
                    var, version, resolution, month
                )
                data_raster = Path(in_dir, f'{name}.tif')
                
                logger.debug((
                    f'{func_name}: loading {var} data from {data_raster} for '
                    f'month {month} at index {idx}'
                ))
  
                gdal.Warp(
                    result, data_raster, 
                    resampleAlg=resample_alg,
                    # dstNodata=-3.4e+38,
                    # outputType=gdal.GDT_Float32,
                )
                pixels = result.ReadAsArray()

                pixels[pixels <= -3e30] = np.nan # fix
                
                new.dataset[var][idx] = pixels # 0based index
                [gc.collect(i) for i in range(2)]

        ## any Unit conversions
        source = 'worldclim'
        for stn, wcn in climate_variables.aliases_for(source, 'dict').items():
            
            if climate_variables.has_conversion(stn, source):
                logger.info(f'{func_name}: converting units for {wcn} to {stn}')
                new.dataset[wcn].values = climate_variables.to_std_units(
                    new.dataset[wcn].values, stn, source
                )

        

        logger.info(f'{func_name}: Renaming variables to standard names...')
        logger.debug(f'{func_name}: Before rename: {list(new.dataset.data_vars)}')
        logger.debug(f'{func_name}: Using aliases: {climate_variables.aliases_for(worldclim.NAME, "dict_r")}')        
        new.dataset = new.dataset.rename(
            climate_variables.aliases_for(worldclim.NAME, 'dict_r')
        )
        logger.debug(f'{func_name}: After rename: {list(new.dataset.data_vars)}') 

        return new
    
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
        funcname = 'TEMDataset.get_by_extent'
        self.logger.info(f'{funcname}: Clip by entent')
        self.logger.debug(f'{funcname}: Starting with extent {minx},{miny},{maxx},{maxy}')
        if self._dataset is None:
            raise errors.UninitializedError(
                "Cannot operate on Uninitialized TEMDataset"
        )

        file_location = None
        if isinstance(self._dataset, Path):
            file_location = self._dataset
            self._dataset = self.dataset
            self.in_memory = True

        lookup = lambda key, default: kwargs[key] if key in kwargs else default
        update_kw = lambda key, default: kwargs.update({key: lookup(key, default)})

        ## gdal kwargs
        update_kw('resample_alg', 'bilinear')
        update_kw('warp_no_data_as_array', False)
        update_kw('gdal_type', gdal.GDT_Float32) ### Probably covert to lookup table, so types are inferred from the dataset
        update_kw('prime_warp', True)
        update_kw('dest_gt', None)
        
        ## general kwarg
        update_kw('resolution', self.resolution)

        resolution = kwargs['resolution']
        if resolution is None:
            raise errors.TEMDatasetMissingResolutionError((
                'get_by_extent needs a resolution, either from kwargs or with '
                'class attribute `resolution` != None'
            ))

        self.logger.debug(f'{funcname}: kwargs: {kwargs}')

        use = lookup('clip_with', 'gdal')
        if use == 'gdal':
            tile = self.get_by_extent_gdal(minx, miny, maxx, maxy, extent_crs, **kwargs) 
        elif use == 'xarray': 
            tile = self.get_by_extent_xr(minx, miny, maxx, maxy, extent_crs, **kwargs) 
        else:
            raise TypeError("get_by_extent: 'clip_with' must be 'gdal', or 'xarray'")
        
        if not file_location is None:
            del(self._dataset)
            self._dataset = file_location
            self.in_memory = False
        
        self.logger.debug(f'{funcname}: ...cleaning up memory at the end of function')
        gc.collect()
        # disabling here leads to ~.15GB memory increase per year.

        self.logger.debug(f'{funcname}: ...calling malloc_trim(0) at the end of function (pass thru lambda if not supported)')
        malloc_trim(0)

        return TEMDataset(tile)
        
    def get_by_extent_gdal(self, minx, miny, maxx, maxy, extent_crs, **kwargs):
        """Returns xr.dataset for use in downscaling

        Parameters
        ----------
        see `clip_by_extent`

        Returns
        -------
        xarrray.Dataset
            subset of data from extent (`minx`,`miny`)(`maxx`,`maxy`) and 
            at `resolution`

        """
        funcname = 'TEMDataset.get_by_extent_gdal'
        
        self.logger.debug(f'{funcname}: Starting with extent {minx},{miny},{maxx},{maxy}')

        working_dataset = self.dataset
        
        resolution = kwargs['resolution']
        nd_as_array = kwargs['warp_no_data_as_array']
        gdal_type = kwargs['gdal_type']
        # print( gdal_type )
        run_primer = kwargs['prime_warp']
        resample_alg = kwargs['resample_alg']
        dest_gt = kwargs['dest_gt']

        ## Clipping with gdal ensures alignment
        ##  1) set up scratch gdal datasets in memory
        ##  1.a) need to find clipped shape, and geotransform from extent/resolution
        ##  1.b) need same from source
        ##  1.c) N time steps from `dataset`
        ##  1.d) bounds in gdal order
        ##  
        ##  2) use gdal warp to clip each var
        ## 
        ##  3) save all to new clipped xr.dataset

        

        # driver = gdal.GetDriverByName("MEM")

        ## clipped shape, and geotransform
        dest_x, dest_y = abs(int((maxx-minx)/resolution[0])), abs(int((maxy-miny)/resolution[1]))
        #dest_gt = minx, resolution, 0.0, miny, 0.0, resolution
        # print(dest_x, dest_y)
        # x_sign, y_sign = 1, 1
        # if dest_x<0:
        #     x_sign = -1
        # if dest_y < 0:
        #     y_sign = -1

        # dest_gt = minx, x_sign*resolution, 0.0, miny, 0.0, y_sign*resolution
        if dest_gt is None:
            # NOTE: assumes north up
            dest_gt = minx, resolution[0], 0.0, maxy, 0.0, resolution[1]    

        if hasattr(working_dataset, 'lat') and hasattr(working_dataset, 'lon'):
            source_x = working_dataset.lon.shape[0]
            source_y = working_dataset.lat.shape[0]
        else: # x and y 
            source_x = working_dataset.x.shape[0]
            source_y = working_dataset.y.shape[0]

        ## read GT from dataset, extra step is to keep resolution positive
        ## which may not be needed on all datasets, so be wary in in future
       
        source_gt = working_dataset.rio.transform()
        # source_gt = source_gt.c, abs(source_gt.a), source_gt.b, source_gt.f, source_gt.d, abs(source_gt.e)
        source_gt = source_gt.c, source_gt.a, source_gt.b, source_gt.f, source_gt.d, source_gt.e
        # print(source_gt)

        # gdal wants things in order, x, y, band count
        # source_dim_sizes = [source_x, source_y]
        # #dest_dim_sizes = [dest_x, dest_y]
        # dest_dim_sizes = [abs(dest_x), abs(dest_y)]

        # N time steps
        if hasattr(working_dataset, 'time') and working_dataset['time'].size > 0:
            n_ts = working_dataset['time'].shape[0]
            # source_dim_sizes.append(n_ts)
            # dest_dim_sizes.append(n_ts)
        else:
            n_ts = 1 # not a time step; in GDAL's view always at least 1 Band.
            # dest_dim_sizes.append(1)
            # source_dim_sizes.append(1)
        self.logger.debug(f'{funcname}: source dimensions (for each Variable): x={source_x}, y={source_y}, time={n_ts}')
        self.logger.debug(f'{funcname}: source GeoTransform: {source_gt}')
        self.logger.debug(f'{funcname}: destination dimensions (for each Variable): x={dest_x}, y={dest_y}, time={n_ts}')
        self.logger.debug(f'{funcname}: destination GeoTransform: {dest_gt}')
        self.logger.debug(f'{funcname}: Resampling Algorithm: {resample_alg}')


        dest_crs = extent_crs.to_wkt()

        # setup dest and soruce
        # dest = driver.Create("", *dest_dim_sizes, gdal_type)
        # dest.SetProjection(dest_crs)
        # dest.SetGeoTransform(dest_gt)
        # dest.FlushCache()
        # print(dest_gt)
        # print(dest_x, dest_y, n_ts)
        dest = gdal_tools.empty_dataset(
            dest_x, dest_y, dest_crs, dest_gt, n_ts, gdal_type
        )
        driver = gdal.GetDriverByName('GTiff')
        driver.CreateCopy('sample-dest.tif', dest)

        source_crs = working_dataset.rio.crs.to_wkt()
        # source = driver.Create("", *source_dim_sizes, gdal_type)
        # source.SetProjection(source_crs)
        # source.SetGeoTransform(source_gt)
        # source.FlushCache() # this should work just once, but when working in 
        #                     # the interpreter, you often have to call it 
        #                     # multiple times.
        source = gdal_tools.empty_dataset(
            source_x, source_y, source_crs, source_gt, n_ts, gdal_type
        )

        # driver = gdal.GetDriverByName('GTiff')
        # driver.CreateCopy('sample-source.tif', source)

        ## option 2
        vars_dict = {var: working_dataset[var].values for var in self.vars }
        data_arrays = gdal_tools.clip_opt_2(dest, source, vars_dict, resample_alg, run_primer, nd_as_array)
        self.logger.debug(f"{funcname}: deleting vars_dict")

        # driver.CreateCopy('sample-dest.tif', dest)
        # driver.CreateCopy('sample-source.tif', source)
        del(vars_dict)

        # Option 1
        # 

        # for var in self.vars:
        #     cur = working_dataset[var]
        #     source.WriteArray(cur.values[:,:,:])
        #     source.FlushCache() ## ensures data is in gdal dataset

        #     dest = gdal_tools.clip_gdal_opt(dest, source, resample_alg, run_primer, nd_as_array)
            
        #     data_arrays[var] = dest.ReadAsArray()

        # option 0
        # data_arrays = {}
        # no_data = np.nan
        # if nd_as_array:
        #     no_data = [np.nan for i in range(n_ts)]

        # for var in self.vars:
        #     cur = working_dataset[var]
        #     source.WriteArray(cur.values[:,:,:])
        #     source.FlushCache() ## ensures data is in gdal dataset

        #     # run twice first to 'prime' the objects, other wise coastal data is
        #     # missing in result
        #     if run_primer:
        #         gdal.Warp(dest, source, multithread=True)
        #     gdal.Warp(
        #         dest, source,
        #         srcNodata=no_data,
        #         dstNodata=no_data,
        #         resampleAlg=resample_alg,
        #         multithread=True
        #     )
        #     dest.FlushCache()
            
        #     data_arrays[var] = dest.ReadAsArray()
            
        ## we want these to be the center of the pixels so for x and y the range
        self.logger.debug(f"{funcname}: ...building xarray Dataset from clipped data")
        res_x = resolution[0]
        x_coords = np.arange(minx+res_x/2, minx + dest_x * res_x, res_x) 
        #y_coords = np.arange(miny+resolution/2, miny + dest_y * resolution, resolution) 

        # print(miny,maxy, resolution)
        res_y = resolution[1]
        # y_coords = np.arange(miny+res_y/2, miny + dest_y * res_y, res_y)
        if res_y > 0:
            # print('a')
            y_coords = np.arange(miny+res_y/2, miny + dest_y * res_y, res_y)
        else: 
            # print('b')
            y_coords = np.arange(maxy+res_y/2, maxy + abs(dest_y) * res_y, res_y)
        # print(y_coords)
        



        coords={
            'x': x_coords,
            'y': y_coords
        }
        dims = ['y', 'x']

        # Handle the time dimension if present. 
        if hasattr(working_dataset, 'time') and working_dataset['time'].size > 0:
            coords['time'] = deepcopy(working_dataset.time.values)
            dims.insert(0, 'time')

        self.logger.debug(f"{funcname}: allocating Dataset")
        tile = xr.Dataset({
            var: xr.DataArray(
                data, dims=dims, coords=coords
            ) for var, data in data_arrays.items()
        })

        for var in self.vars:
            tile[var].attrs.update(working_dataset[var].attrs)

        self.logger.debug(f"{funcname}: writing spatial metadata to Dataset")
        tile.rio.write_crs(
            dest_crs, 
            inplace=True
        )
        self.logger.debug(f"{funcname}: writing coordinate system to Dataset in place")
        tile.rio.write_transform(Affine.from_gdal(*dest_gt), inplace=True)

        self.logger.debug(f"{funcname}: cleaning up gdal source and dest datasets")
        del(source)
        del(dest)
        self.logger.debug(f"{funcname}: ...forcing garbage collection" )
        gc.collect()
        self.logger.debug(f"{funcname}: ...trimming malloc'd memory (pass thru lambda on some systems...)" )
        malloc_trim(0)

        return tile

    def get_by_extent_xr(self, minx, miny, maxx, maxy, extent_crs, **kwargs):
        """Returns xr.dataset for use in downscaling

        Parameters
        ----------
        see `clip_by_extent`

        Returns
        -------
        xarrray.Dataset
            subset of data from extent (`minx`,`miny`)(`maxx`,`maxy`) and 
            at `resolution`

        """
        working_dataset = self.dataset
        resolution = kwargs['resolution'][0] # only use one here

        if extent_crs != working_dataset.rio.crs:
            local_dataset = working_dataset.rio.reproject(extent_crs)
        else:
            local_dataset = working_dataset

        if minx>maxx:
            print('swap x')
            minx, maxx = maxx,minx
        if miny>maxy:
            print('swap y')
            miny, maxy = maxy,miny  
                
            
        if hasattr(local_dataset, 'lat') and hasattr(local_dataset, 'lon'):
            mask_x = ( local_dataset.lon >= minx ) & ( local_dataset.lon <= maxx )
            mask_y = ( local_dataset.lat >= miny ) & ( local_dataset.lat <= maxy )
            
            full_minx = int(local_dataset.lon.values[0])
            full_miny = int(local_dataset.lat.values[0])
            
            full_maxx = int(local_dataset.lon.values[-1])
            full_maxy = int(local_dataset.lat.values[-1])
        else: # x and y 
            mask_x = ( local_dataset.x >= minx ) & ( local_dataset.x <= maxx )
            mask_y = ( local_dataset.y >= miny ) & ( local_dataset.y <= maxy )
            
            full_minx = int(local_dataset.x.values[0])
            full_miny = int(local_dataset.y.values[0])
            
            full_maxx = int(local_dataset.x.values[-1])
            full_maxy = int(local_dataset.y.values[-1])

        tile = local_dataset.where(mask_x&mask_y, drop=True)

        
        # if tile.rio.crs.to_epsg() != 4326:
        #     tile = tile.rename({'lat':'y', 'lon':'x'})
        ## TODO update to handle lat lon dim names
        tile = tile.rio.set_spatial_dims(x_dim="x", y_dim="y", inplace=True)\
                    .rio.write_crs(extent_crs, inplace=True)\
                    .rio.write_coordinate_system(inplace=True) 
        # else:
        #     tile = tile.rio.write_crs(extent_crs, inplace=True)\
        #            .rio.write_coordinate_system(inplace=True)

        pad_minx = max(0, int((full_minx - minx)//resolution))
        pad_miny = max(0, int((full_miny - miny)//resolution))        
        pad_maxx = max(0,int((maxx - full_maxx)//resolution))
        pad_maxy = max(0,int((maxy - full_maxy)//resolution))

        if not(pad_minx ==pad_miny == pad_maxx == pad_maxy==0):

            tile = tile.pad({'x':(pad_minx, pad_maxx),'y':(pad_miny, pad_maxy)})
            c_x, c_y = int((maxx-minx)/resolution), int((maxy-miny)/resolution)
            x_coords = np.arange(minx+resolution/2, minx + c_x * resolution, resolution) 
            y_coords = np.arange(miny+resolution/2, miny + c_y * resolution, resolution) 
            tile = tile.assign_coords({'x':x_coords, 'y':y_coords})
            ## have to redo this here
            tile = tile.rio.set_spatial_dims(x_dim="x", y_dim="y", inplace=True)\
                     .rio.write_crs(extent_crs, inplace=True)\
                     .rio.write_coordinate_system(inplace=True) 

        return tile
 
    def save(self, out_file, **kwargs): 
        """Save `dataset` as a netCDF file.

        Parameters
        ----------
        out_file: path
            file to save
        **kwargs: dict
            'climate_encoding': dict
                custom climate encoding for saved .nc files,
                if not provided encoding is generated from other
                kwargs
            'missing_value': float, default 1.e+20
            'fill_value': float, default 1.e+20
                values set as _FillValue, and missing_value in netCDF variable
                headers
            'overwrite': bool
                when true overwrite existing files
            'zlib': bool
                When True compression is used in encoding
            'complevel': int
                Compression level for 'zlib'
            'extra_attrs': dict
                any extra attributes to add to `dataset` before saving
                as .nc file

        Raises
        -------
        errors.UninitializedError:
            if self._dataset is None
        """
        if self._dataset is None:
            raise errors.UninitializedError(
                "Cannot save Uninitialized TEMDataset"
            )
        
        if self.in_memory == False:
            raise IOError("We don't support saving when `in_memory` == False")

        def lookup(kw, ke, de):
            return kw[ke] if ke in kw else de

        fill_value = lookup(kwargs, 'fill_value', 1.0e+20 )
        missing_value = lookup(kwargs, 'missing_value', 1.0e+20 )
        compress = lookup(kwargs, 'use_zlib', True)
        complevel = lookup(kwargs, 'complevel', 9)
        overwrite = lookup(kwargs, 'overwrite', False)
        extra_attrs = lookup(kwargs, 'extra_attrs', {})

        ## fixes all the weird rio stuff
        crs = self.dataset.spatial_ref.attrs['spatial_ref']
        x_dim = 'x'
        y_dim = 'y'
        if CRS(crs) == CRS('EPSG:4326'): #is this true for other crs as well?
            x_dim ='lon'
            y_dim = 'lat'
        self.dataset = self.dataset.rio.write_crs(crs, inplace=True).\
                 rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim, inplace=True).\
                 rio.write_coordinate_system(inplace=True) 
        
        self.dataset = self.dataset.rio.write_crs(crs, inplace=True).\
                 rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim, inplace=True).\
                 rio.write_coordinate_system(inplace=True) 



        # self.set_climate_encoding(**kwargs)
        if 'climate_encoding' in kwargs:            
            climate_enc = kwargs['climate_encoding']
        else:
            climate_enc = {
                '_FillValue':fill_value, 
                'missing_value':missing_value, 
                'zlib': compress, 'complevel': complevel # USE COMPRESSION?
            }
        
        for _var in self.vars:
            self.dataset[_var].rio.update_encoding(climate_enc, inplace=True)
            
        self.dataset.attrs.update(TEMDS_version = Version())
        self.dataset.attrs.update(extra_attrs)

        unlimited_dims = None    
        if 'unlimited_dims' in kwargs:
            unlimited_dims = kwargs['unlimited_dims']

        if  not Path(out_file).exists() or overwrite:
            
            Path(out_file).parent.mkdir(parents=True, exist_ok=True)
            Path(out_file).unlink(missing_ok=True)
            self.dataset.to_netcdf(
                    out_file, 
                    # encoding=encoding, 
                    engine="netcdf4",
                    unlimited_dims=unlimited_dims
                )
        else:
            raise FileExistsError(
                f'The file {out_file} exists and `overwrite` is False'
            )

    def load(self, in_path, **kwargs):
        """Loads existing .nc dataset formatted for temds. Dataloaded 
        with this function should be able to pass `verify` 

        Parameters
        ----------
        in_path: Path
            path to netcdf file
        **kwargs: dict
            'force_aoi_to': str
                Variable name to force all other variables to have the 
                same no_data pixels
            'aoi_nodata': float, defaults np.nan
                no data value to used with 'force_aoi_to'
            chunks: int
                passed to xr.open_dataset cunks argumet
        
        Returns
        -------
        When `in_memory` is false retuns an open `xr.Dataset`
        """
        func_name ='TEMDdataset.load'
        self.logger.info(f'{func_name}: reading {in_path}')
        
        lookup = lambda kw, ke, de: kw[ke] if ke in kw else de
        # year_override = lookup(kwargs, 'year_override', None)
        force_aoi_to = lookup(kwargs, 'force_aoi_to', None)
        aoi_nodata = lookup(kwargs, 'aoi_nodata', np.nan)
        kwargs_crs = lookup(kwargs, 'crs', None) 
        chunks = lookup(kwargs, 'chunks', None)

        self.logger.debug(f'{func_name}: loading dataset {chunks=}')
        in_dataset = xr.open_dataset(
            in_path, engine="netcdf4", chunks=chunks
        )

        if 'spatial_ref' in in_dataset:
            if 'crs_wkt' in in_dataset['spatial_ref'].attrs:
                self.logger.warn(f"{func_name}: Dataset is carrying CRS info: {in_dataset['spatial_ref'].attrs['crs_wkt'][0:50]}...")
                self.logger.warn(f"Ignoring crs passed in kwargs: ({kwargs_crs=})")
                crs = in_dataset['spatial_ref'].attrs['crs_wkt']
            else:
                self.logger.warn(f"{func_name}: Dataset has spatial_ref attribute, but does not have crs_wkt.")
                self.logger.warn(f"Using crs passed in kwargs: ({kwargs_crs=})")
                crs = kwargs_crs
        else:
            self.logger.warn(f"{func_name}: Dataset is missing CRS info.")
            self.logger.warn(f"Using crs passed in kwargs: ({kwargs_crs=})")
            crs = kwargs_crs

        ## BUGGY with dask multiprocess
        if force_aoi_to is not None:
            self.logger.debug((
                f'{func_name}: force AOI to {force_aoi_to} '
                'AOI for all vars'
            ))
            aoi_idx = np.isnan(in_dataset[force_aoi_to].values)
            mask = aoi_idx.astype(float)
            mask[mask == 1] = aoi_nodata
            in_dataset = in_dataset + mask

        x_dim = 'x'
        y_dim = 'y'

        if 'lon' in in_dataset and 'lat' in in_dataset:
            if CRS(crs) == CRS('EPSG:4326'): #is this true for other crs as well?
                x_dim = 'lon'
                y_dim = 'lat'
            else:
                self.logger.info("Dataset has lon/lat dimensions but crs is not EPSG:4326. Using default x, y spatial dimensions.")
        else:
            self.logger.info("Dataset is missing lon/lat dimensions. Using default x, y spatial dimensions.")


        # # trickery to ensure all data uses our standard min coords
        s_minx, s_miny, s_maxx, s_maxy = in_dataset.rio.bounds()
        transform = in_dataset.rio.transform()
        if transform.c > s_minx:
            transform = Affine(abs(transform.a), transform.b, s_minx, transform.d, abs(transform.e), s_miny)
            if x_dim == 'x':
                in_dataset = in_dataset.reindex(x=in_dataset.x[::-1])
            else:
                in_dataset = in_dataset.reindex(lon=in_dataset.lon[::-1])
            in_dataset = in_dataset.rio.write_transform(transform, inplace=True)

                
        if transform.f > s_miny:
            transform = Affine(abs(transform.a), transform.b, s_minx, transform.d, abs(transform.e), s_miny)
            if y_dim == 'y':
                in_dataset = in_dataset.reindex(y=in_dataset.y[::-1])
            else:
                in_dataset = in_dataset.reindex(lat=in_dataset.lat[::-1])
            in_dataset = in_dataset.rio.write_transform(transform, inplace=True)
        


        in_dataset = \
            in_dataset.rio.write_crs(crs, inplace=True).\
                 rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim, inplace=True).\
                 rio.write_coordinate_system(inplace=True) 

        in_dataset = \
            in_dataset.rio.write_crs(crs, inplace=True).\
                 rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim, inplace=True).\
                 rio.write_coordinate_system(inplace=True) 
        self.logger.debug(f'{func_name}: ...collecting garbage at end of load...')
        gc.collect()
        malloc_trim(0)
        if self.in_memory :
            self.logger.debug(f'{func_name}: loading data into memory...')
            self._dataset=in_dataset
            self.logger.debug(f'{func_name}: dataset initialized')
        else:
            self.logger.debug(f'{func_name}: dataset not loaded into memory, returning lazy loaded dataset...')
            return in_dataset
    
    def verify(self):
        """Verifies Internal data is in correct format for downscale process

        Returns
        -------
        tuple: (bool, list)
            bool is true when verification passes, otherwise false
            list is a list of reasons for failure, when bool is false 
        """
        verified = True
        reasons = []

        valid_names = climate_variables.temds_names()
        for var in self.vars:
            if var not in valid_names:
                verified = False
                reasons.append(f'{var} is not a TEMDS supported variable')

        for var, units in self.units.items():
            std_units = climate_variables.temds_units_for(var)
            if units != std_units:
                verified = False
                reasons.append(f'{var} has units {units} but needs {std_units}')

        return verified, reasons
    
    def check_dataset_with_nan_mask(self, mask):
        matches = {}
        for var in self.dataset.data_vars:
            matches[var] = bool((np.isnan(self.dataset[var].sum(axis=0, skipna=False)) == mask).all().values)
        return bool(np.array([v for k, v in matches.items()]).all()), matches
    
    def check_number_timesteps(self, expected=365):
        correct = self.dataset.time.shape[0] == expected
        missing = []
        if not correct:
            missing = [] # TODO
        return correct, missing

    def fill_outliers(self, var, mean, std, n_std):
        in_range_ix = ~(
            (self.dataset[var] > mean + n_std * std) | \
            (self.dataset[var] < mean - n_std * std)
        )
        # keeps values were idx is true, replaces others with mean
        updated = self.dataset[var].where(in_range_ix, mean) 
        self.dataset[var] = updated

    def fill_out_of_bounds(self, var, value, which, fill):
        if which == 'lower':
            op = operator.lt
        else:
            op = operator.gt
        ix = op(self.dataset[var], value) 
        # return ix
        if ix.any():
            # print('filling')
            updated = self.dataset[var].where(
                ix | np.isnan(self.dataset[var]), # don't fill nans
                fill 
            ) 
            self.dataset[var] = updated

class YearlyDataset(TEMDataset):
    """This sub class of TEMDataset represents daily data
    for a single year.  Extends TEMDataset by adding
    `year` attribute.

    Attributes
    ----------
    year: int
        Year the data represnets
    """

    def __init__(self, year, dataset, in_memory=True, logger=Logger(), **kwargs):
        """
        Parameters
        ----------
        year: int or None
            Year the data represnets
            if None `year` is infered
        See `TEMDataset` for remaining parameters

        Raises
        -------    
        errors.YearUnknownError
            if `year` cannot be infered
        """
        self.year = year
        super().__init__(dataset, in_memory, logger, **kwargs)

        if self.year is None and 'year_override_callback' in kwargs:
            self.year = int(kwargs['year_override_callback'](dataset.name))
        else:
            try: 
                self.year = self.dataset.attrs['data_year']
            except KeyError:
                pass 
        
        if self.year is None:
            raise errors.YearUnknownError("year could not be set in init")
                

    @staticmethod
    def from_TEMDataset(inds, year, logger=Logger()):
        """converts an existing TEMDataset to YearlyDataset

        Parameters
        ----------
        inds: TEMDataset
            A TEMDataset
        year: int
            Year for the data

        Returns
        -------
        YearlyDataset
        """
        kwargs = {}
        kwargs['logger'] = inds.logger
        kwargs['in_memory'] = inds.in_memory
        new = YearlyDataset(year, inds.dataset, **kwargs)
        new._cached_load_kwargs = inds._cached_load_kwargs  
        return new
    
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
    
    def from_cmip6(year, data_path,
            elevation = 0,
            download=False,
            variables = 'all',
            models=[],
            experiments=[],
            ensambles=[],
            extent=None,
            logger=Logger(),
            calcualte_vapo=False,
            file_name_match = '*.nc'
        ):
        """
        TODO add region option?
        """
        func_name = "YearlyDataset.from_cmip6"
        table=['day']

        if variables=='all':
            variables = cmip6.SOURCE_VARS

        params = {
            'models': models,
            'variables': variables,
            'experiment': experiments,
            'table': table,
            'ensemble': ensambles,

        }
        logger.debug(f'dapper Params: {params}')
        

        # available = cmip_utils.find_available_data(params)
        # logger.info(f'YearlyDataset.from_cmip6: found {available.shape[0]} datasets')
        # if available.shape[0] == 0:
        #     msg = (
        #         'YearlyDataset.from_cmip6: requested cmip6 datasets not found.'
        #         'Check your arguments for models, expiremnts, etc.'
        #     )
        #     logger.error(msg)
        #     raise errors.YearlyTimeSeriesError(msg)


        # lat_bounds=None
        # lon_bounds=None
        # if not extent is None:
        #     lon_bounds = (extent.minx, extent.maxx)
        #     lat_bounds = (extent.miny, extent.maxy)

        # if download:
        #     cmip_utils.download_pangeo(
        #         available, data_path, lat_bounds=lat_bounds, lon_bounds=lon_bounds
        #     )

        


        ready_variables = []
        for var_file in Path(data_path).glob(file_name_match ):
            # logger.debug(f'checking: {var_file}')
            # print(var_file)
            # var, model, experiment, ensamble = var_file.stem.split('_')
            var =  var_file.stem.split('-')[-1]
            # if not var in variables:
            #     # print('var')
            #     continue
            # if models != [] and not model in models:
            #     # print('model')
            #     continue
            # if experiments != [] and not experiment in experiments:
            #     # print('exp')
            #     continue
            # if ensambles != [] and not ensamble in ensambles:
            #     # print(ensamble, ensambles)
            #     # print('ens', ensambles != [],not ensamble in ensambles)
            #     continue
            logger.debug(f'processing: {var_file}')

            data =  xr.open_dataset(var_file)
            data = data.sel(time=slice(f'{year}-01-01', f'{year}-12-31'))
            gt = data.rio.transform()
            ## Drop original encoding as we will redo this 
            ## to match our other data
            data = data.drop_encoding()

            ## this does change lon_bnds as well, but why?
            data.coords['lon'] = (data.coords['lon'] + 180) % 360 - 180
            data.coords['lon_bnds'] = (data.coords['lon_bnds'] + 180) % 360 - 180

            data = data.sortby(data.lon)
            

            ready_variables.append(data)
        logger.info(f'YearlyDataset.from_cmip6: datasets open = {len(ready_variables)}')
        
        try:
            data = xr.merge(ready_variables)
        except xr.MergeError:   # needs this sometimes?
            data = xr.merge(ready_variables, compat='override')
        # return data
        
        # return data
        ## we use 'noleap' calender
        data = data.convert_calendar('noleap')
        if data.time.size != 365:
            msg = (
                'YearlyDataset.from_cmip6: full year of data(noleap) not '
                f'found for year: {year}, N timestps was {data.time.size}. '
                'It should be 365. Check if data is available for the year '
                'in CMIP6 experiment being used'
            )
            logger.error(msg)
            raise errors.YearlyTimeSeriesError(msg)

        new = YearlyDataset(year, data, logger=logger)

        source = cmip6.NAME
        for std_var, var in climate_variables.aliases_for(source, 'dict').items():
            if climate_variables.has_conversion(std_var, source):
                logger.info(f'{func_name}: Converting units for {var} to {std_var}')
                new.dataset[var].values = climate_variables.to_std_units(
                    new.dataset[var].values, std_var, source
                )
            cv = climate_variables.lookup_alias(source, var)
            unit = str(cv.std_unit)
            # print(unit)
            v_name = cv.name
            new.dataset[var].attrs.update(units=unit, name=v_name)

        if calcualte_vapo:
            new.dataset = cmip6.callback_psl_to_vapo(new.dataset, logger, elevation=elevation)

        new.dataset = new.dataset.rename(
            climate_variables.aliases_for(cmip6.NAME, 'dict_r')
        )
  
        verified, reasons = new.verify()
        if not verified:
            logger.warn(f'YearlyDataset.from_preprocess_crujra: verificaion issues: {reasons}')

        # data is in wgs84; is it always though?
        new.dataset.rio.write_crs('EPSG:4326', inplace=True)\
            .rio.set_spatial_dims(x_dim='lon', y_dim='lat', inplace=True)\
            .rio.write_coordinate_system(inplace=True)
        new.dataset.rio.write_crs('EPSG:4326', inplace=True)\
            .rio.set_spatial_dims(x_dim='lon', y_dim='lat', inplace=True)\
            .rio.write_coordinate_system(inplace=True)
        
        # gt = (-180.0, 1.8617204339585491, 0.0, 83.75, 0.0, -1.8617204339523812)
        new.dataset.rio.write_transform(gt, inplace=True)

        return new

        
    @staticmethod
    def from_explicit_fire(year, data_path=None, synthetic=True, 
                           extent_raster_path=None, 
                           logger=Logger()):
        func_name = "TEMdataset.from_explicit_fire"
        logger.info(f'{func_name}: Processing explicit fire data')   

        if extent_raster_path is None:
            raise ValueError(f'{func_name}: extent_raster_path is required!')
        
        if data_path is not None:
            raise NotImplementedError(f'{func_name}: data_path not yet implemented!')
        if not synthetic:
            raise NotImplementedError(f'{func_name}: non-synthetic data not yet implemented!')

        logger.info(f'{func_name}: Using extent from {extent_raster_path}')
        extent_raster = gdal.Open(extent_raster_path)

        logger.info(f'{func_name}: Creating empty xarray dataset...')
        newDS = TEMDataset.from_raster_extent(extent_raster_path, 
                                      in_vars='exp_burn_mask exp_jday_of_burn exp_severity exp_area_of_burn'.split(' '),
                                      ds_time_dim=['time'], buffer_px=0)

        new = YearlyDataset.from_TEMDataset(newDS, year)

        from IPython import embed; embed()

        # ### Monthly information
        # month = list(range(1, 13, 1))
        # monthlength=[31,28,31,30,31,30,31,31,30,31,30,31]
        # first_day_of_month_noleap=[1,32,60,91,121,152,182,213,244,274,305,335]
        # first_day_of_month_leap=[1,33,61,92,122,153,183,214,245,275,306,336]
        # #data = {'month': month, 'doy_noleap': first_day_of_month_noleap, 'doy_leap': first_day_of_month_leap, 'length': monthlength}
        # data = {'month': month, 'doy_noleap': first_day_of_month_noleap, 'length': monthlength}
        # month_info = pd.DataFrame(data)


        # if synthetic:
        #     logger.info(f'{func_name}: Generating synthetic data arrays...')
        #     fire_occurrence = np.zeros(shape=(extent_raster.RasterYSize, extent_raster.RasterXSize))
        #     fire_severity = np.ones(shape=(extent_raster.RasterYSize, extent_raster.RasterXSize))*2
        #     fire_jday_of_burn = np.ones(shape=(extent_raster.RasterYSize, extent_raster.RasterXSize))+160
        #     fire_area_of_burn = np.ones(shape=(extent_raster.RasterYSize, extent_raster.RasterXSize))*1
        # else:
        #     raise NotImplementedError(f'{func_name}: Non-synthetic data not yet implemented!')




    @staticmethod
    def from_crujra(year, data_path, 
                    is_preprocessed = False,
                    extent=None, 
                    logger=Logger(),
                    crujra_version = '2.5',
                    sorted_by_var = True, 
                    ):
        """Loads source CRUJRA files to YearlyDataset. Data sould be local
        in `data_path` but can be unziped or in .gz form. 

        An option to load data processed in TEMDS<=0.1.0 is also present

        Parameters
        ----------
        data_path: path
            a directory containing raw cru jra files to be loaded by matching
            file_format, or a netcdf file if `is_preprocesed` is True
        is_preprocessed: bool, defaults False
            If True, `data_path` is a netcdf file created by the previous 
            versions of TEMDS. TEMDS<=0.1.0
        extent: DataFrame, Optional
            Dataframe with minx, miny, maxx, maxy fields. Extent to
            clip data to.
        logger: logger.Logger, defaults to new object
            Logger to use for printing or saving messages
            The default Logger will not print any messages, but a 
            text file may be created from it by calling `logger.save`
        crujra_version: str, defaults '2.5'
        sorted_by_var: Bool, defauts True
            When True files in `data_path` are sorted in to subdirectories 
            by variable
            Otherwise, files are in same directory

        Returns
        -------
        YearlyDataset
            Can pass `verify`
        """
        func_name = "YearlyDataset.from_crujra"
        
        # is_preprocessed flag can be used to modify pre standard 
        # data that is alreay daily, with all vars
        if is_preprocessed:
            logger.info(f'{func_name}: loading preprocessed {data_path}')
            new = YearlyDataset(None, data_path, logger=logger)
        else:
            logger.info(f"{func_name}: Loading from raw data at '{data_path}'")
            ### TODO: assumes Data is local, we may wan't to add some download 
            # logic
            
            cleanup = False
            datasets = {}
            for var in crujra.SOURCE_VARS:
                var_file = f'{crujra.name_for(var, year, crujra_version)}.nc'
                var_path = Path(data_path, var_file)
                if sorted_by_var:
                    var_path = Path(data_path, var, var_file)

                if not var_path.exists():
                    gz_path = Path(var_path.parent, f'{var_path.name}.gz')
                    file_tools.extract(gz_path)
                    cleanup = True

                            
                logger.info(f"{func_name}: loading raw data for '{var}' from '{var_path}'")
                temp = xr.open_dataset(var_path, engine="netcdf4")
                

                if extent is not None:
                    logger.info(f'{func_name}: clipping {var} to aoi')
                    mask_x =  ( temp.lon >= extent.minx ) \
                            & ( temp.lon <= extent.maxx  )
                    mask_y =  ( temp.lat >= extent.miny ) \
                            & ( temp.lat <= extent.maxy )
                    temp = temp.where(mask_x & mask_y, drop=True)

                method = crujra.RESAMPLE_LOOKUP[var]
                logger.info(f'{func_name}: resampling 6hr {var} to daily by {method}')
                datasets[var] = climate_variables.RESAMPLE_METHODS[method](temp)
                datasets[var].attrs.update(cell_methods=f'time:{method}')
        
            new = YearlyDataset(year, datasets[crujra.SOURCE_VARS[0]], logger=logger)
            new.dataset = new.dataset.assign({var: datasets[var][var] for var in datasets})
            
            if cleanup:
                for var in crujra.SOURCE_VARS:
                    var_file = f'{crujra.name_for(var, year, crujra_version)}.nc'
                    var_path = Path(data_path, var_file)
                    if sorted_by_var:
                        var_path = Path(data_path, var, var_file)
                    var_path.unlink()
        

        
        # convert units;
        ## NOTE  precip just has incorrect units assinged
        ## so we just change the name here
        var = 'pre'
        cv = climate_variables.lookup_alias(crujra.NAME, var)
        unit = str(cv.std_unit)
        # print(unit)
        v_name = cv.name
        new.dataset[var].attrs.update(units=unit, name=v_name)

        source = crujra.NAME
        for std_var, var in climate_variables.aliases_for(source, 'dict').items():
            if climate_variables.has_conversion(std_var, source):
                logger.info(f'{func_name}: Converting units for {var} to {std_var}')
                new.dataset[var].values = climate_variables.to_std_units(
                    new.dataset[var].values, std_var, source
                )
                cv = climate_variables.lookup_alias(crujra.NAME, var)
                unit = cv.std_unit.name
                v_name = cv.name
                new.dataset[var].attrs.update(units=unit, name=v_name)

        ## calculate VAPO
        logger.info(f'{func_name}: Calculating vapo kPa')
        pres = new.dataset['pres']
        spfh = new.dataset['spfh']
        new.dataset['vapo'] = climate_variables.calculate_vapo(pres, spfh)
        unit = climate_variables.CLIMATE_VARIABLES['vapo'].std_unit.name
        v_name = climate_variables.CLIMATE_VARIABLES['vapo'].name
        new.dataset['vapo'].attrs.update(units=unit, name=v_name)

        # ## calculate wind + wind dir
        ugrd = new.dataset['ugrd']
        vgrd = new.dataset['vgrd']

        logger.info(f'{func_name}: Calculating wind from components')
        new.dataset['wind'] = crujra.calculate_wind(ugrd, vgrd)
        unit = climate_variables.CLIMATE_VARIABLES['wind'].std_unit.name
        v_name = climate_variables.CLIMATE_VARIABLES['wind'].name
        new.dataset['wind'].attrs.update(units=unit, name=v_name)
        
        logger.info(f'{func_name}: Calculating winddir from components')
        new.dataset['winddir'] = crujra.calculate_winddir(ugrd, vgrd)
        unit = climate_variables.CLIMATE_VARIABLES['winddir'].std_unit.name
        v_name = climate_variables.CLIMATE_VARIABLES['winddir'].name
        new.dataset['winddir'].attrs.update(units=unit, name=v_name)
        

        logger.info(f'{func_name}: Renaming variables to TEMDS standard names...')
        logger.info(f'{func_name}: current names: {list(new.dataset.data_vars)}')
        logger.info(f'{func_name}: {climate_variables.aliases_for(crujra.NAME, "dict_r")}')
        new.dataset = new.dataset.rename(
            climate_variables.aliases_for(crujra.NAME, 'dict_r')
        )
        logger.info(f'{func_name}: new names: {list(new.dataset.data_vars)}')

        verified, reasons = new.verify()
        if not verified:
            logger.warn(f'YearlyDataset.from_preprocess_crujra: verificaion issues: {reasons}')
        return new

    def save(self, out_file, **kwargs): 
        """Extends save to save `year` as 'data_year' in netcdf
        attrs.

        Parameters
        ----------
        Same as `TEMDataset.save`
        """
        if 'extra_attrs' in kwargs:
            kwargs['extra_attrs']['data_year'] = self.year
        else:
            kwargs['extra_attrs'] = {'data_year': self.year}

        kwargs['unlimited_dims'] = ['time']

        super().save(out_file, **kwargs)


    def load(self, in_path, **kwargs):
        """Extends load to support `year`, which should be presnet in
        netcdf file as 'data_year' attr

        Parameters
        ----------
        Same as `TEMDataset.load` with additonal kwarg 'year_overried'
        'year_overried': function, defualts None
            function to find year in file name, TODO: Depricate

        Returns
        -------
        When `in_memory` is false retuns an open `xr.Dataset`
        """
        lookup = lambda kw, ke, de: kw[ke] if ke in kw else de
        year_override = lookup(kwargs, 'year_override', None)

        in_dataset = super().load(in_path, **kwargs)
        if self.in_memory:
            in_dataset = self._dataset
        

        try: 
            if self.year is None and year_override is None:
                self.year = int(in_dataset.attrs['data_year'])
            elif type(year_override) is int:
                self.year = year_override
        except KeyError:
            raise errors.YearUnknownError(
                f"Cannot load year from nc file {in_path}. "
                "Missing 'data_year' attribute"
            )
        
        if not self.in_memory:
            return in_dataset

    
    def synthesize_to_monthly(self, target_vars, new_names=None):
        """Converts target_vars to monthly data (12 time steps). In other words,
        resample daily data to monthly data using the method specified in
        target_vars.

        This AnnualDaily object is expected to have daily data for a single year.
        The target_vars is a dictionary where the keys are the variable names
        and the values are the methods to use for conversion, either 'mean' or
        'sum'. The new_names parameter is a dictionary that maps the variable
        names in the new dataset to the desired names.

        Parameters
        ----------
        target_vars: dict
            vars to convert to monthly data, and the methods to use for
            conversion 'mean', or 'sum': i. e. {'nirr': 'mean', 'prec': 'sum'}
        new_names: dict
            Maps var names in new dataset i.e: {'nirr':'nirr', 'prec':'precip'}

        Returns
        -------
        xr.Dataset:
            With 12 time steps.
        """
        #TODO: support target vars == None or 'all' and run all vars

        # TODO: experiment/confirm resampling to month-middle ('M' vs 'MS') and
        # see if the results are different...

        # Note: Tried re-writing this to do the resampling after concatenating, 
        # thinking this might change the numbers around the year boundaries, but 
        # it didn't seem to make a difference and was slower to run...

        monthly = xr.Dataset()

        for var, method in target_vars.items():
            if method == 'mean':
                monthly[var] = self.dataset[var].resample(time='MS').mean()
            elif method == 'sum':
                monthly[var] = self.dataset[var].resample(time='MS').sum(skipna = False)
            else:
                raise TypeError (f'method {method} not supported in synthesize_to_monthly')

        if new_names is not None:
            monthly = monthly.rename(new_names)

        return monthly
    
    def verify(self):
        """Overloads verify to check for year, See parent docs"""
        verified, reasons = super().verify()
        if self.year is None:
            verified = False
            reasons.apped('YearlyDataset.year is None')
        return verified, reasons


    def get_by_extent(self, minx, miny, maxx, maxy, extent_crs, **kwargs):
        """Overloads get_by_extent for year, See parent docs"""
        return YearlyDataset.from_TEMDataset(
            super().get_by_extent(minx, miny, maxx, maxy, extent_crs, **kwargs),
            self.year
        ) 

    
    def drop_leap_days(self):
        idx = ~((self.dataset.time.dt.month == 2) & (self.dataset.time.dt.day == 29))
        temp = self.dataset.sel(time=idx)
        self.dataset = temp
