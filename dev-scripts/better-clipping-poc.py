"""
Proof of concept for fixing alignment in clipping tiles with gdal
"""
from temds.datasources import worldclim
from temds.datasources import crujra

from pathlib import Path

import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from osgeo import gdal

import gc


## UPDATE THIS IF RUNNING LOCALLY
data_root = Path('...')


tiles_HV = [(7,15),(7, 16),(8,15),(8,16)]

tile_index = gpd.read_file(data_root.joinpath('00-aoi/tile-index/'))
cru_arctic = crujra.AnnualDaily(1970, data_root.joinpath('02-arctic/cru-jra-fixed/crujra.arctic.v2.5.5d.1970.365d.noc.nc'))


def select_tile(c_idx, tile_index_gdf):
    hdx = tile_index_gdf['H'] == c_idx[0]
    vdx = tile_index_gdf['V'] == c_idx[1]
    return tile_index_gdf[vdx & hdx].bounds


def tile_bounds_as_tuple(bounds_df):
    minx, maxx, miny, maxy = bounds_df[['minx','maxx','miny','maxy']].iloc[0]
    return minx, maxx, miny, maxy


minx, maxx, miny, maxy = tile_bounds_as_tuple(select_tile((7,16), tile_index))
buffer_area = 4000*20
minx = minx - buffer_area
miny = miny - buffer_area
maxx = maxx + buffer_area
maxy = maxy + buffer_area

## pulled from data for tile (7,16)
wc_tf = (-1758000.0, 4000.0, 0.0, 2835000.0, 0.0,4000.0)

## pulled from data for tile (7,16)
y, x = (140, 109)

### Setup in memory gdal datasets for dest and source
driver = gdal.GetDriverByName("MEM")
dest = driver.Create("", x, y, 365, gdal.GDT_Float32)
dest.SetProjection(tile_index.crs.to_wkt())
dest.SetGeoTransform(wc_tf)
dest.FlushCache()


example = cru_arctic.dataset['tmax']
cru_tf = example.rio.transform().to_gdal()

bnds, srcx, srcy = example.shape
source = driver.Create("", srcy, srcx, bnds, gdal.GDT_Float32)
source.SetProjection(example.rio.crs.to_wkt())

source.SetGeoTransform(cru_tf )
source.FlushCache()
source.WriteArray(example.values[:,:,:])
source.FlushCache()

## This is sometimes needed to ensure edge (costal) pixels are downscaled
## correctly
gdal.Warp(
    dest, source,
    # resampleAlg='bilinear',
    # dstNodata=np.nan,
    # srcNodata=np.nan,

)

gdal.Warp(
    dest, source,
    resampleAlg='bilinear',
    dstNodata=np.nan,
    srcNodata=np.nan,

)
dest.FlushCache()

plt.imshow(dest.ReadAsArray()[0])
plt.title('CRU-tile-tmax')
plt.show()

np.save('good-tmax-7-16.data.npy', dest.ReadAsArray())
z = gdal.Translate('example-tmax-7-16.tif', dest)
del(z)