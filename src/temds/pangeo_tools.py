import intake
import intake_esm # I think this needs to be here
import fsspec
import xarray as xr
import cftime
import numpy as np
from pathlib import Path

CMIP6_CATALOG_URL = "https://storage.googleapis.com/cmip6/pangeo-cmip6.json"


def connect(url=CMIP6_CATALOG_URL):
    """Connect to pango catalog via intake esm

    Parameters
    ----------
    url: str
        url to json catalog

    Returns
    -------
    intake_esm.core.esm_datastore
    """
    return intake.open_esm_datastore(url)

def search(catalog, parameters):
    """Search catalog for scenarios/models/variables/etc.

    Parameters
    ----------
    catalog: intake_esm.core.esm_datastore
        catalog of available data
    parameters: dict
        Search parameters 
        example:
        parameters = {
            "experiment_id": [ 'ssp126','ssp245', 'ssp370', 'ssp585' ],
            "table_id": ["day"],
            "variable_id": ['tas'],
            "member_id": ["r4i1p1f1"],
            "source_id": ["CESM2"],
            "grid_label": ["gn"],
        }

    Returns
    -------
    intake_esm.core.esm_datastore
        catalog with search applied
    """
    return catalog.search(**parameters)

def download(save_to, zstore, time_bounds, spatial_bounds, **kwargs):
    """Download data

    Parameters
    ----------
    save_to: Path
        Where to save locally 
    zstore: str
        Gs id od zarr to connect to
    time_bounds: tuple(cftime, cftime)
        Bounds on time variable to save 
        Lower bound is inclusive, and upper bound is exclusive
    spatial_bounds: tuple(float, float, float, float)
        spatial bounds to save
        (minx, miny, maxx, maxy)
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
    
    Returns
    -------
    xr.Dataset
    """
    time_coder = xr.coding.times.CFDatetimeCoder(use_cftime=True)
    ds = xr.open_zarr(
        fsspec.get_mapper(zstore, token="anon", access="read_only"),
        consolidated=True,
        decode_times=time_coder,
    )
    time_idx = np.logical_and(ds.time>=time_bounds[0], ds.time<time_bounds[1])
    
    minx, miny, maxx, maxy = spatial_bounds
    sidx_x =  np.logical_and(ds.lon >= minx, ds.lon <= maxx)
    sidx_y =  np.logical_and(ds.lat >= miny, ds.lat <= maxy)
    spatial_idx = np.logical_and(sidx_x, sidx_y)

    print('clipping to extents')
    ds = ds.where(np.logical_and(time_idx, spatial_idx), drop=True)

    def lookup(kw, ke, de):
        return kw[ke] if ke in kw else de

    fill_value = lookup(kwargs, 'fill_value', 1.0e+20 )
    missing_value = lookup(kwargs, 'missing_value', 1.0e+20 )
    compress = lookup(kwargs, 'use_zlib', True)
    complevel = lookup(kwargs, 'complevel', 9)
    overwrite = lookup(kwargs, 'overwrite', False)
    extra_attrs = lookup(kwargs, 'extra_attrs', {})

    if 'climate_encoding' in kwargs:            
        climate_enc = kwargs['climate_encoding']
    else:
        climate_enc = {
            '_FillValue':fill_value, 
            'missing_value':missing_value, 
            'zlib': compress, 'complevel': complevel # USE COMPRESSION?
        }

    for var in ds.data_vars:
        ds[var].rio.update_encoding(climate_enc, inplace=True)
    ds.rio.write_crs('EPSG:4326',inplace=True)\
        .rio.set_spatial_dims(x_dim='lon', y_dim='lat', inplace=True)
    
    ds.coords['lon'] = (ds.coords['lon'] + 180) % 360 - 180
    ds.coords['lon_bnds'] = (ds.coords['lon_bnds'] + 180) % 360 - 180
    print('saving')
    if  not Path(save_to).exists() or overwrite:
        Path(save_to).parent.mkdir(parents=True, exist_ok=True)
        Path(save_to).unlink(missing_ok=True)
        ds.to_netcdf(save_to, engine="netcdf4")
    else:
        raise FileExistsError(
            f'The file {save_to} exists and `overwrite` is False'
        )
    return ds
