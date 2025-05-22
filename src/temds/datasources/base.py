"""
Base
----

Base class for all .nc based data type
"""
from pathlib import Path

import xarray as xr
import rioxarray  # activate 
from abc import ABCMeta, abstractmethod

from .errors import TEMDataSetUninitializeError

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
        self.dataset = dataset
        self.verbose = verbose
        self.vars = _vars
        
    
    def get_by_extent(self, minx, maxx, miny, maxy, extent_crs, **kwargs):
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
        if self.dataset is None:
            raise TEMDataSetUninitializeError()

        resolution = kwargs['resolution'] if 'resolution' in kwargs else None
        flip_y = kwargs['flip_y'] if 'flip_y' in kwargs else False
        flip_x = kwargs['flip_x'] if 'flip_x' in kwargs else False


        if extent_crs != self.dataset.rio.crs:
            local_dataset = self.dataset.rio.reproject(extent_crs)
        else:
            local_dataset = self.dataset

        if minx>maxx:
            print('swap x')
            minx, maxx = maxx,minx
        if miny>maxy:
            print('swap y')
            miny, maxy = maxy,miny  
                
            
        if hasattr(local_dataset, 'lat') and hasattr(local_dataset, 'lon'):
            print('ll')
            mask_x = ( local_dataset.lon >= minx ) & ( local_dataset.lon <= maxx )
            mask_y = ( local_dataset.lat >= miny ) & ( local_dataset.lat <= maxy )
        else: # x and y 
            mask_x = ( local_dataset.x >= minx ) & ( local_dataset.x <= maxx )
            mask_y = ( local_dataset.y >= miny ) & ( local_dataset.y <= maxy )
            
        tile = local_dataset.where(mask_x&mask_y, drop=True)

        if tile.rio.crs.to_epsg() != 4326:
            tile = tile.rename({'lat':'y', 'lon':'x'})

            tile = tile.rio.set_spatial_dims(x_dim="x", y_dim="y", inplace=True)\
                     .rio.write_crs(extent_crs, inplace=True)\
                     .rio.write_coordinate_system(inplace=True) 

            if flip_y: 
                tile = tile.reindex(y=list(reversed(tile.y)))
            if flip_x:
                tile = tile.reindex(x=list(reversed(tile.x)))
        else:
            tile = tile.rio.write_crs(extent_crs, inplace=True)\
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
            

        if not Path(out_file).exists() or overwrite:
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