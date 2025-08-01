"""
dataset
-------

Objects to manage data for TEMDS project

"""
from pathlib import Path
from copy import deepcopy
import gc

import xarray as xr
import numpy as np
import rioxarray  # activate 
from osgeo import gdal
from affine import Affine
from pyproj import CRS
from cf_units import Unit

from . import errors
from . import worldclim, crujra
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
    logger: logger.Logger
        Logger to use for printing or saving messages

    Properties
    ----------
    dataset:
        Provides access to internal `_dataset`, the getter
        will always provided access to an in memory version
        of the data. If `in_memory` is False the in memory 
        dataset is read only.
    """
    def __init__(self, dataset, in_memory=True, logger=Logger(), **kwargs):
        """
        Parameters
        ----------
        dataset: xr.dataset or Path
            the dataset
        in_memory: Bool
        logger: logger.Logger, defaults to new object
            Logger to use for printing or saving messages

        """
        self._dataset = None

        self.logger = logger
        
        self.in_memory = in_memory
        self.cached_load_kwargs={}

        if isinstance(dataset, xr.Dataset):
            self.dataset=dataset
        else: # Path
            dataset = Path(dataset)
            if dataset.exists() and dataset.suffix == '.nc':
                
                if in_memory:
                    self.load(dataset, **kwargs)
                else:
                    self.dataset = dataset
                    self.cached_load_kwargs = kwargs

            else:
                raise IOError('input data is missing or not a .nc file')
        
    @property
    def crs(self):
        """Property for Quick access to crs"""
        return CRS(self.dataset.rio.crs)
    
    @property
    def transform(self):
        """Property for Quick access to geo transform"""
        return self.dataset.rio.transform()

    @property
    def resolution(self):
        """Property for Quick access to resolution"""
        return self.dataset.rio.resolution()
    
    @property
    def extent(self):
        """Property for Quick access to resolution"""
        return self.dataset.rio.bounds()

    @property
    def vars(self):
        """Property for quick access to variables in dataset
        """
        return list(self.dataset.data_vars)
    
    @property
    def units(self):
        """Property for quick access to units for variables in dataset
        """
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
            return self.load(self._dataset, **self.cached_load_kwargs)
        else:
            raise TypeError('Bad Dataset Type')

    @dataset.setter
    def dataset(self, value):
        """Setting of dataset property."""
        self._dataset = value

    @staticmethod
    def from_raster_extent(raster, in_vars = [], ds_time_dim=[], buffer_px=30, logger=Logger()):
        """
        TODO: update
        Creates new xr.dataset for `self.dataset` using 
        the extent, transform, and projection of `raster`. Also includes a
        buffer, which ends up being helpful in downstream operations.
        `self.dataset` resolution and extent are calculated from `rasters`
        transform.

        Parameters
        ----------
        raster: path
            path to a raster file that can be opened as a gdal dataset
        """
        func_name = 'TEMdataset.from_raster_extent'
        logger.info(f'{func_name}: Initializing with extent from {raster}')
        extent_ds = gdal.Open(raster)

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
        miny = gt[3] - (buffer_px * extent_ds.RasterYSize)
        maxx = minx + gt[1] * extent_ds.RasterXSize + (buffer_px * extent_ds.RasterXSize)
        maxy = miny + gt[5] * extent_ds.RasterYSize + (buffer_px * extent_ds.RasterYSize)
        
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
    
        y_array = np.arange( miny, maxy, abs(y_res) ) + (abs(y_res)/2)
        # lat_dim is empty if this is true, so swap min and max and redo
        if maxy < miny: 
            miny, maxy = maxy, miny
            y_array = np.arange(miny,maxy, abs(y_res)) + (abs(y_res)/2)
            miny, maxy = maxy, miny ## keep for gdal

        ## do we need the dimension trick here?
        x_array = np.arange(minx, maxx, abs(x_res)) + (abs(x_res)/2)
        rows, cols = len(y_array), len(x_array)
        dims = ['time', y_dim, x_dim]
        n_time = len(ds_time_dim)
        shape = [n_time, rows, cols]

        empty_data = np.zeros(n_time * rows * cols)\
                       .reshape(shape).astype('float32')
        data_vars = { 
            var : (dims, deepcopy(empty_data) ) for var in in_vars
        }

        ## the deep copy is to prevent shared memory issues
        ## might not be necessary here, but included just in
        ## case
        coords={
            y_dim: y_array, 
            x_dim: x_array,
            'time': deepcopy(ds_time_dim)
        }

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
    def from_worldclim(
            data_path, 
            download=False, 
            version='2.1', 
            resolution='30s', 
            in_vars='all', 
            extent_raster=None,
            overwrite=False, 
            logger=Logger(),
            resample_alg='bilinear'
        ):
        """"""
        ## used in messages.
        func_name = "TEMdataset.from_worldclim"
        
        if in_vars == 'all':
            in_vars = worldclim.VARS
        if not type(in_vars) is list:
            in_vars = [in_vars]
        completed = {}
        logger.info(f'{func_name}: Processing Worldclim data in {data_path}')

        ## download first if needed
        if download: # get from web
            logger.info(f'{func_name}: Downloading data.')
            for var in in_vars:
                url = worldclim.url_for(var, version, resolution)
                logger.debug(f'{func_name}: downloading {url}')
                file_tools.download(url, data_path, overwrite)


        #get available data, unzip if needed
        for var in in_vars:
            var_dir = worldclim.name_for(var, version, resolution)
            in_dir = Path(f'{data_path}/{var_dir}')
            if not in_dir.exists():
                archive = Path(f'{data_path}/{var_dir}.zip')
                logger.debug(f'{func_name}: unzipping {archive}')
                file_tools.extract(archive, in_dir)
            completed[var] = in_dir

        logger.debug(
            f'{func_name}: Initializing with extent from {extent_raster}'
        )
        if extent_raster is None:
            key = list(completed.keys())[0]
            extent_raster = list(completed[key].glob('*.tif'))[0]
        
        new = YearlyDataset.from_raster_extent(
            extent_raster, 
            in_vars=in_vars, 
            ds_time_dim=MONTH_START_DAYS, 
            logger=logger
        )

        x_dim = 'x'
        y_dim = 'y'
        if new.crs == CRS.from_epsg(4326): #is this true for other crs as well?
            x_dim ='lon'
            y_dim = 'lat'


        gt = new.transform.to_gdal()
        minx, miny = gt[0], gt[3]
        maxx = minx + abs(gt[1]) * new.dataset[x_dim].size
        maxy = miny + abs(gt[5]) * new.dataset[y_dim].size
        extent = (minx, miny, maxx, maxy) #_warp_order
        logger.info(
            f'{func_name}: Running gdal.Warp to extent {extent} on all data'
        )
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
                
                # load result to memory so we don't have temp files
                result = gdal.Warp(
                    '', data_raster, 
                    xRes=abs(gt[1]), yRes=abs(gt[5]),
                    outputBounds=extent,
                    dstSRS=new.crs.to_wkt(),
                    format='mem',
                    resampleAlg=resample_alg,
                    dstNodata=-3.4e+38,
                    outputType=gdal.GDT_Float32,
                )
                pixels = result.ReadAsArray()
                if gt[5] < 0: # filp flop if res_y is negative
                    pixels = pixels[::-1]
                    
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


        new.dataset = new.dataset.rename(
            climate_variables.aliases_for(worldclim.NAME, 'dict_r')
        )

        return new
    
    def __repr__(self):
        """string representation"""
        return(f"{type(self).__module__}.{type(self).__name__}")

    def get_by_extent(self, minx, miny, maxx, maxy, extent_crs, **kwargs):
        """Returns xr.dataset for use in downscaling

        Parameters
        ----------
        minx: Float
            Minimum x coord, in `self.dataset` projection
        maxx: Float
            Maximum x coord, in `self.dataset` projection
        miny: Float
            Minimum y coord, in `self.dataset` projection
        maxy: Float
            Maximum y coord, in `self.dataset` projection
        resolution: float, Optional
            Resolution of dataset to return, If None, The resolution is
            not changed from `self.dataset`

        Returns
        -------
        xarrray.Dataset
            subset of data from extent (`minx`,`miny`)(`maxx`,`maxy`) and 
            at `resolution`

        """
        if self._dataset is None:
            raise errors.UninitializedError(
                "Cannot operate on Uninitialized TEMDataset"
        )


        lookup = lambda key, default: kwargs[key] if key in kwargs else default
        update_kw = lambda key, default: kwargs.update({key: lookup(key, default)})

        # This is a relic of some previous bugs...it seems that now, if you load
        # a dataset, it loads the correct direction and writes out in the 
        # correction orientation. So flip_y and flip_x are no longer needed.
        # flip_y = lookup('flip_y', False)
        # flip_x = lookup('flip_x', False)

        ## gdal kwargs
        update_kw('resample_alg', 'bilinear')
        update_kw('warp_no_data_as_array', False)
        update_kw('gdal_type', gdal.GDT_Float32) ### Probably covert to lookup table, so types are inferred from the dataset
        update_kw('prime_warp', True)
        
        ## general kwarg
        update_kw('resolution', self.resolution)

        resolution = kwargs['resolution']
        if resolution is None:
            raise errors.TEMDatasetMissingResolutionError((
                'get_by_extent needs a resolution, either from kwargs or with '
                'class attribute `resolution` != None'
            ))

        self.logger.debug(f'TEMDataset.get_by_extent kwargs: {kwargs}')

        use = lookup('clip_with', 'gdal')
        if use == 'gdal':
            tile = self.get_by_extent_gdal(minx, miny, maxx, maxy, extent_crs, **kwargs) 
        elif use == 'xarray': 
            tile = self.get_by_extent_xr(minx, miny, maxx, maxy, extent_crs, **kwargs) 
        else:
            raise TypeError("get_by_extent: 'clip_with' must be 'gdal', or 'xarray'")
        gc.collect()
        malloc_trim(0)
        # if flip_y: 
        #     tile = tile.reindex(y=list(reversed(tile.y)))
        # if flip_x:
        #     tile = tile.reindex(x=list(reversed(tile.x)))
        return TEMDataset(tile)
        
    def get_by_extent_gdal(self, minx, miny, maxx, maxy, extent_crs, **kwargs):
        """Returns xr.dataset for use in downscaling

        Parameters
        ----------
        minx: Float
            Minimum x coord, in `self.dataset` projection
        maxx: Float
            Maximum x coord, in `self.dataset` projection
        miny: Float
            Minimum y coord, in `self.dataset` projection
        maxy: Float
            Maximum y coord, in `self.dataset` projection
        resolution: float, Optional
            Resolution of dataset to return, If None, The resolution is
            not changed from `self.dataset`

        Returns
        -------
        xarrray.Dataset
            subset of data from extent (`minx`,`miny`)(`maxx`,`maxy`) and 
            at `resolution`

        """
        # print('gdal')
        working_dataset = self.dataset

        resolution = kwargs['resolution']
        nd_as_array = kwargs['warp_no_data_as_array']
        gdal_type = kwargs['gdal_type']
        run_primer = kwargs['prime_warp']
        resample_alg = kwargs['resample_alg']

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
        driver = gdal.GetDriverByName("MEM")

        ## clipped shape, and geotransform
        c_x, c_y = int((maxx-minx)/resolution), int((maxy-miny)/resolution)
        c_gt = minx, resolution, 0.0, miny, 0.0, resolution

        if hasattr(working_dataset, 'lat') and hasattr(working_dataset, 'lon'):
            s_x = working_dataset.lon.shape[0]
            s_y = working_dataset.lat.shape[0]
        else: # x and y 
            s_x = working_dataset.x.shape[0]
            s_y = working_dataset.y.shape[0]

        ## read GT from dataset, extra step is to keep resolution positive
        ## which may not be needed on all datasets, so be wary in in future
        s_gt = working_dataset.rio.transform()
        s_gt = s_gt.c, abs(s_gt.a), s_gt.b, s_gt.f, s_gt.d, abs(s_gt.e)
        
        
        # N time steps
        n_ts = working_dataset['time'].shape[0]

    
        self.logger.debug(f'TEMDataset.get_by_extent_gdal: source dimensions (for each Variable): x={s_x}, y={s_y}, time={n_ts}')
        self.logger.debug(f'TEMDataset.get_by_extent_gdal: source GeoTransform: {s_gt}')
        self.logger.debug(f'TEMDataset.get_by_extent_gdal: destination dimensions (for each Variable): x={c_x}, y={c_y}, time={n_ts}')
        self.logger.debug(f'TEMDataset.get_by_extent_gdal: destination GeoTransform: {c_gt}')
        self.logger.debug(f'TEMDataset.get_by_extent_gdal: Resampling Algorithm: {resample_alg}')


        dest_crs = extent_crs.to_wkt()

        # setup dest and soruce
        dest = driver.Create("", c_x, c_y, n_ts, gdal_type)
        dest.SetProjection(dest_crs)
        dest.SetGeoTransform(c_gt)
        dest.FlushCache()

        source_crs = working_dataset.rio.crs.to_wkt()
        source = driver.Create("", s_x, s_y, n_ts, gdal_type)
        source.SetProjection(source_crs)
        source.SetGeoTransform(s_gt)
        
        source.FlushCache()
        ## opption 2
        vars_dict = {var: self.dataset[var].values for var in self.vars }
        data_arrays = gdal_tools.clip_opt_2 (dest, source, vars_dict, resample_alg, run_primer, nd_as_array)
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
            
        ## we want these to be teh center of the pixels so for x and y the range
        x_coords = np.arange(minx+resolution/2, minx + c_x * resolution, resolution) 
        y_coords = np.arange(miny+resolution/2, miny + c_y * resolution, resolution) 

        coords={
            'time': deepcopy(working_dataset.time.values), 
            'x': x_coords,
            'y': y_coords
        }

        tile = xr.Dataset({
            var: xr.DataArray(
                data, dims=['time','y','x'], coords=coords 
            ) for var, data in data_arrays.items()
        })
        tile.rio.write_crs(
            dest_crs, 
            inplace=True
        )
        tile.rio.write_transform(Affine.from_gdal(*c_gt), inplace=True)
        del(source)
        del(dest)
        gc.collect()
        malloc_trim(0)
        return tile

    def get_by_extent_xr(self, minx, miny, maxx, maxy, extent_crs, **kwargs):
        """Returns xr.dataset for use in downscaling

        Parameters
        ----------
        minx: Float
            Minimum x coord, in `self.dataset` projection
        maxx: Float
            Maximum x coord, in `self.dataset` projection
        miny: Float
            Minimum y coord, in `self.dataset` projection
        maxy: Float
            Maximum y coord, in `self.dataset` projection
        resolution: float, Optional
            Resolution of dataset to return, If None, The resolution is
            not changed from `self.dataset`

        Returns
        -------
        xarrray.Dataset
            subset of data from extent (`minx`,`miny`)(`maxx`,`maxy`) and 
            at `resolution`

        """
        working_dataset = self.dataset
        resolution = kwargs['resolution']

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
        May contain:
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

        if  not Path(out_file).exists() or overwrite:
            Path(out_file).parent.mkdir(parents=True, exist_ok=True)
            self.dataset.to_netcdf(
                    out_file, 
                    # encoding=encoding, 
                    engine="netcdf4",
                    # unlimited_dims={'time':True}
                )
        else:
            raise FileExistsError(
                f'The file {out_file} exists and `overwrite` is False'
            )

    def load(self, in_path, **kwargs):
        """Loads existing .nc dataset formatted for temds.
        """
        func_name ='TEMDdataset.load'
        self.logger.info(f'{func_name}: reading {in_path}')
        
        lookup = lambda kw, ke, de: kw[ke] if ke in kw else de
        # year_override = lookup(kwargs, 'year_override', None)
        force_aoi_to = lookup(kwargs, 'force_aoi_to', None)
        aoi_nodata = lookup(kwargs, 'aoi_nodata', np.nan)
        # crs = lookup(kwargs, 'crs', 'EPSG:4326')
        chunks = lookup(kwargs, 'chunks', None)

        self.logger.debug(f'{func_name}: loading dataset {chunks=}')
        in_dataset = xr.open_dataset(
            in_path, engine="netcdf4", chunks=chunks
        )

        crs = in_dataset.spatial_ref.attrs['spatial_ref']

        ## BUGGY with dask multiprocess
        if not force_aoi_to is None:
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
        if CRS(crs) == CRS('EPSG:4326'): #is this true for other crs as well?
            x_dim ='lon'
            y_dim = 'lat'
        in_dataset = \
            in_dataset.rio.write_crs(crs, inplace=True).\
                 rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim, inplace=True).\
                 rio.write_coordinate_system(inplace=True) 

        in_dataset = \
            in_dataset.rio.write_crs(crs, inplace=True).\
                 rio.set_spatial_dims(x_dim=x_dim, y_dim=y_dim, inplace=True).\
                 rio.write_coordinate_system(inplace=True) 
        
        gc.collect()
        malloc_trim(0)
        if self.in_memory :
            self._dataset=in_dataset
            self.logger.debug(f'{func_name}: dataset initialized')
        else:
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


class YearlyDataset(TEMDataset):
    """This sub class of TEMDataset represents daily data
    for a single year.  Extends TEMDataset by adding
    `year` attribute.
    """

    def __init__(self, year, dataset, in_memory=True, logger=Logger(), **kwargs):
        self.year = year
        super().__init__(dataset, in_memory, logger, **kwargs)

        if self.year is None and 'year_override_callback' in kwargs:
            self.year = int(kwargs['year_override_callback'](dataset.name))
        else:
            self.logger.suspend = True
            try: 
                self.year = self.dataset.attrs['data_year']
            except KeyError:
                pass 
            self.logger.suspend = False
        
        if self.year is None:
            raise errors.YearUnknownError("year could not be set in init")
                

    @staticmethod
    def from_TEMDataset(inds, year):
        """converts an existing TEMDataset to YearlyDataset
        """
        kwargs = {}
        kwargs['logger'] = inds.logger
        kwargs['in_memory'] = inds.in_memory
        new = YearlyDataset(year, inds.dataset, **kwargs)
        new.cached_load_kwargs = inds.cached_load_kwargs  
        return new

    @staticmethod
    def from_crujra(year, data_path, 
                    is_preprocessed = False,
                    extent=None, 
                    logger=Logger(),
                    crujra_version = '2.5',
                    sorted_by_var = True, 
                    ):
        """Loads raw (direct from source) CRU JRA files, resamples to a daily
        timestep, and clips to an extent if provided. The raw data is expected to 
        be have been downloaded from CRU in the .gz compressed format.
        The files are expected to have following format for names:
            "{var}/crujra.v2.5.5d.{var}.{yr}.365d.noc.nc.gz"
        where {var} is the variable name and {yr} is the year of data.
        The raw data is expected to be in a directory structure where each
        variable is in a subdirectory named after the variable name. Each CRU 
        file is expected to have a time dimension with a calendar attribute of
        '365_day' or 'noleap' and be at a 6 hour resolution.

        Parameters
        ----------
        data_path: path
            a directory containing raw cru jra files to be loaded by matching
            file_format. 
        aoi_extent: tuple, optional
            clipping extent(minx, miny, maxx, maxy) geo-coordinates in 
            degrees(WGS84) # is this really the order we want?
        file_format: str, defaults None
            string that contains {var} and {yr} formatters to match. When 
            None is passed, '{var}/crujra.v2.5.5d.{var}.{yr}.365d.noc.nc.gz' 
            pattern is used; this format matches CUR JRA file format conventions
            where each variable is nested in a {var} subdirectory at the root 
            `data_path`
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
        unit = cv.std_unit.name
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
        new.dataset['vapo'] = crujra.calculate_vapo(pres, spfh)
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
        

        new.dataset = new.dataset.rename(
            climate_variables.aliases_for(crujra.NAME, 'dict_r')
        )
        verified, reasons = new.verify()
        if not verified:
            logger.warn(f'YearlyDataset.from_preprocess_crujra: verificaion issues: {reasons}')
        return new

    def save(self, out_file, **kwargs): 
        """
        """
        if 'extra_attrs' in kwargs:
            kwargs['extra_attrs']['data_year'] = self.year
        else:
            kwargs['extra_attrs'] = {'data_year': self.year}

        super().save(out_file, **kwargs)


    def load(self, in_path, **kwargs):
        """Load with year code added
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

    def __repr__(self):
        return(f"{type(self).__module__}.{type(self).__name__}: {self.year}")

    def __lt__(self, other):
        """less than for sort
        """
        if self.year is None or other.year is None:
            raise errors.YearUnknownError(
                "An item in comparison is missing 'year' attribute"
            )
        return self.year < other.year

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
                monthly[var] = self.dataset[var].resample(time='MS').sum()
            else:
                raise TypeError (f'method {method} not supported in AnnualDaily.synthesize_to_monthly')

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
        return YearlyDataset.from_TEMDataset(
            super().get_by_extent(minx, miny, maxx, maxy, extent_crs, **kwargs),
            self.year
        ) 