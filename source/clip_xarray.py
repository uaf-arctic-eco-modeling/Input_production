"""
Clip Xarray
-----------

utility function for clipping xarray dataset

Can likely be refactored into some sort of base class for crujra and 
worldclim at some point
"""
import rioxarray #  is it needed here?


def clip_xr_dataset(dataset, minx, miny, maxx, maxy, resolution=None):
    """Clips xr.dataset to an extent(`minx`,`miny`)(`maxx`,`maxy`) 


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
        not changed from `self.dataset` (not implemented)

    Returns
    -------
    xarray.dataset
        subset of data from extent (`minx`,`miny`)(`maxx`,`maxy`) and 
        at `resolution`
    """
    
    if minx>maxx:
        print('swap x')
        minx, maxx = maxx,minx
    if miny>maxy:
        print('swap y')
        miny, maxy = maxy,miny  
        

    mask_x =  ( dataset.lon >= minx ) \
            & ( dataset.lon <= maxx )
    mask_y =  ( dataset.lat >= miny ) \
            & ( dataset.lat <= maxy )
    tile = dataset.where(mask_x&mask_y, drop=True)
    tile.rio.write_crs(dataset.rio.crs, inplace=True)
    ## adjust resolution #TODO add some checks and implement based on
    ## commented code, Currently no resolution changes are needed

    # from rasterio.enums import Resampling
    # tile_rs = tile.rio.reproject(
    #     tile.rio.crs,
    #     resolution=(1000, 1000),
    #     resampling=Resampling.bilinear,
    # )



    return tile
