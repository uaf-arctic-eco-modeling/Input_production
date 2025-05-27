"""
Base
----

Base class for all .nc based data type
"""
from pathlib import Path
from abc import ABCMeta, abstractmethod
from copy import deepcopy
import gc

import xarray as xr
import numpy as np
import rioxarray  # activate 
from osgeo import gdal
from affine import Affine

from . import errors

import matplotlib.pyplot as plt

gdal.UseExceptions()

from functools import cache

try:
    import ctypes
    libc = ctypes.CDLL("libc.so.6") # clearing cache 
    malloc_trim = libc.malloc_trim
except:
    malloc_trim = lambda x: x ## do nothing 


@cache
def clip_gdal_opt(dest, source, resample_alg, run_primer, nd_as_array):
    no_data = np.nan
    if nd_as_array:
        no_data = [np.nan for i in range(source.RasterCount)]

    if run_primer:
        gdal.Warp(dest, source, warpOptions =['NUM_THREADS=4'],)#multithread=True)
    gdal.Warp(
        dest, source,
        srcNodata=no_data,
        dstNodata=no_data,
        resampleAlg=resample_alg,
        warpOptions =['NUM_THREADS=4'],
        # multithread=True
    )
    dest.FlushCache()
    return dest

#cant cache dict
def clip_opt_2 (dest, source, vars_dict, resample_alg, run_primer, nd_as_array):
    data_arrays = {}
    no_data = np.nan
    if nd_as_array:
        no_data = [np.nan for i in range(source.RasterCount)]

    for var in vars_dict:
        cur = vars_dict[var]
        source.WriteArray(cur)
        source.FlushCache() ## ensures data is in gdal dataset

        # run twice first to 'prime' the objects, other wise coastal data is
        # missing in result
        # dest = clip_gdal_opt(dest, source, resample_alg, run_primer, no_data)
        if run_primer:
            gdal.Warp(dest, source, multithread=True)
        gdal.Warp(
            dest, source,
            srcNodata=no_data,
            dstNodata=no_data,
            resampleAlg=resample_alg,
            multithread=True
        )
        dest.FlushCache()
        
        data_arrays[var] = dest.ReadAsArray()
    return data_arrays

class TEMDataSet(object):
    """Base class for temds .nc representations
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self, dataset=None, _vars=None, verbose=False):
        """
        Inheriting objects need these attributes,

        __init__ should be implemented fully for each
        """
        self._dataset = dataset
        self.verbose = verbose
        self.vars = _vars
        self.resolution = None# default Project Resoloution
        self.cached_load_kwargs={}

    @property
    def dataset(self):
        if isinstance(self._dataset, xr.Dataset):
            return self._dataset
        elif isinstance(self._dataset, Path):
            return self.load(self._dataset, **self.cached_load_kwargs)
        else:
            raise TypeError('Bad Dataset Type')

    @dataset.setter
    def dataset(self, value):
        self._dataset = value

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
            raise errors.TEMDataSetUninitializeError()


        lookup = lambda key, default: kwargs[key] if key in kwargs else default
        update_kw = lambda key, default: kwargs.update({key: lookup(key, default)})

        
        flip_x = lookup('flip_y', False)
        flip_y = lookup('flip_x', False)

        ## gdal kwargs
        update_kw('resample_alg', 'bilinear')
        update_kw('warp_no_data_as_array', False)
        update_kw('gdal_type',gdal.GDT_Float32)### Probably covert to lookup table, so types are inferred from the dataset
        update_kw('prime_warp', True)
        
        ## general kwarg
        update_kw('resolution', self.resolution)

        resolution = kwargs['resolution']
        if resolution is None:
            raise errors.TEMDataSetMissingResolutionError(
                'get_by_extent needs a resolution, either from kwargs or with class attribute `resolution` != None'
            )

        if self.verbose: print(kwargs)

        use = lookup('clip_with', 'gdal')
        if use == 'gdal':
            tile = self.get_by_extent_gdal(minx, miny, maxx, maxy, extent_crs, **kwargs) 
        elif use == 'xarray': 
            tile = self.get_by_extent_xr(minx, miny, maxx, maxy, extent_crs, **kwargs) 
        else:
            raise TypeError("get_by_extent: 'clip_with' must be 'gdal', or 'xarray'")
        gc.collect()
        malloc_trim(0)
        if flip_y: 
            tile = tile.reindex(y=list(reversed(tile.y)))
        if flip_x:
            tile = tile.reindex(x=list(reversed(tile.x)))
        return tile
        

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
        ##  1.a) need to clipped find shape, abd geotransform from extent/resolution
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

        if self.verbose: 
            print(f'source dimensions (for each Variable): x={s_x}, y={s_y}, time={n_ts}')
            print(f'source GeoTransform: {s_gt}')
            print(f'destination dimensions (for each Variable): x={c_x}, y={c_y}, time={n_ts}')
            print(f'destination GeoTransform: {c_gt}')
            print(f'Resampling Algorithm: {resample_alg}')


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
        data_arrays = clip_opt_2 (dest, source, vars_dict, resample_alg, run_primer, nd_as_array)
        del(vars_dict)

        # Option 1
        # 

        # for var in self.vars:
        #     cur = working_dataset[var]
        #     source.WriteArray(cur.values[:,:,:])
        #     source.FlushCache() ## ensures data is in gdal dataset

        #     dest = clip_gdal_opt(dest, source, resample_alg, run_primer, nd_as_array)
            
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

        
        if tile.rio.crs.to_epsg() != 4326:
            tile = tile.rename({'lat':'y', 'lon':'x'})

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
        if self.dataset is None:
            raise TEMDataSetUninitializeError()

        lookup = lambda kw, ke, de: kw[ke] if ke in kw else de

        fill_value = lookup(kwargs, 'fill_value', 1.0e+20 )
        missing_value = lookup(kwargs, 'missing_value', 1.0e+20 )
        compress = lookup(kwargs, 'use_zlib', True)
        complevel = lookup(kwargs, 'complevel', 9)
        overwrite = lookup(kwargs, 'overwrite', False)

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

    # def set_climate_encoding(self, **kwargs):
    #     lookup = lambda kw, ke, de: kw[ke] if ke in kw else de

    #     fill_value = lookup(kwargs, 'fill_value', 1.0e+20 )
    #     missing_value = lookup(kwargs, 'missing_value', 1.0e+20 )
    #     compress = lookup(kwargs, 'use_zlib', True)
    #     complevel = lookup(kwargs, 'complevel', 9)
    #     # overwrite = lookup(kwargs, 'overwrite', False)

    #     if 'climate_encoding' in kwargs:            
    #         climate_enc = kwargs['climate_encoding']
    #     else:
    #         climate_enc = {
    #             '_FillValue':fill_value, 
    #             'missing_value':missing_value, 
    #             'zlib': compress, 'complevel': complevel # USE COMPRESSION?
    #         }
        
    #     for _var in self.vars:
    #         self.dataset[_var].rio.update_encoding(climate_enc, inplace=True)


