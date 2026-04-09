"""
Sub-Region
----------

Subregion generator object

"""
from pathlib import Path

import shapely
import geopandas as gpd
from osgeo import gdal
import pyproj
import yaml



from ..gdal_tools import empty_dataset
from .. import corrections, downscalers

from ..logger import Logger
from ..datasources import dataset, timeseries

from .mask import Mask
from .region import Region
from .tools import mask_boundary_compatibility_report

class MaskBoundaryCompatibilityError(Exception):
    """Exception for region mask and  boundary incompatibility errors
    """
    pass

class TileSizeTooBigError(Exception):
    """
    """
    pass

class SubregionGenerator(object):
    def __init__(self, full_region, tile_size_x=100, tile_size_y=100):
        self.full_region = full_region
        self.tile_size_x = tile_size_x
        self.tile_size_y = tile_size_y
        self.tile_index = self._create_tile_index()
        
    def get_tile_gridsize(self):
    
        maskX = self.full_region.mask.raster.RasterXSize
        maskY = self.full_region.mask.raster.RasterYSize
        
        N_TILES_X = int(maskX / self.tile_size_x)
        N_TILES_Y = int(maskY / self.tile_size_y)
        
        if maskX % self.tile_size_x > 0:
            N_TILES_X += 1
        
        if maskX % self.tile_size_y > 0:
            N_TILES_Y += 1
        
        return N_TILES_X, N_TILES_Y

    def _create_tile_index(self):
        '''
        Chop a raster up into tiles.
        Returns list of tile extent dictionaries. Each dict will have x, y, minx
        and max (projection coords) and H and V indices in the tileset. And the
        resolution.
        '''
        maskX = self.full_region.mask.raster.RasterXSize
        maskY = self.full_region.mask.raster.RasterYSize
    
        aoiGT = self.full_region.mask.raster.GetGeoTransform()
        geotransform = aoiGT
        
        minx = geotransform[0]
        miny = geotransform[3]
        maxx = minx + geotransform[1] * maskX
        maxy = miny + geotransform[5] * maskY
        aoi_extents = dict(minx=minx, miny=miny, maxx=maxx, maxy=maxy)
    
        
    
        N_tiles_X, N_tiles_Y = self.get_tile_gridsize()
        if N_tiles_X == 1 and N_tiles_Y==1:
           raise TileSizeTooBigError('Subdividing this region with input tile_size_x, and tile_size_y is unnecessary as it would only create 1 tile')
    
        tile_extents = []
    
        for h in range(N_tiles_X):
          for v in range(N_tiles_Y):
    
            tile_xmin = aoi_extents['minx'] + self.tile_size_x * h * aoiGT[1]
            if (h+1) == len(range(N_tiles_X)):
              tile_xmax = tile_xmin + (maskX % self.tile_size_x) * aoiGT[1]
            else:
              tile_xmax = tile_xmin + self.tile_size_x * aoiGT[1]
    
            tile_pixelXsize = aoiGT[1]
            tile_pixelYsize = aoiGT[5]
    
            # Origin LOWER LEFT
            tile_ymin = aoi_extents['miny'] + tile_pixelYsize * maskY \
                        + self.tile_size_y * v * tile_pixelYsize * -1
            if (v+1) == len(range(N_tiles_Y)):
              tile_ymax = tile_ymin + (maskY % self.tile_size_y) * tile_pixelYsize * -1
            else:
              tile_ymax = tile_ymin + self.tile_size_y * tile_pixelYsize * -1 
    
            # # Origin UPPER LEFT 
            # tile_ymin = aoi_extents['miny'] + TILE_SIZE_Y * v * aoiGT[5]
            # if (v+1) == len(range(N_tiles_Y)):
            #   tile_ymax = tile_ymin + (maskY % TILE_SIZE_Y) * aoiGT[5]
            # else:
            #   tile_ymax = tile_ymin + TILE_SIZE_Y * aoiGT[5]
    
            tile_extents.append(dict(
                H=h, V=v, 
                geometry = shapely.box(tile_xmin, tile_ymin, tile_xmax, tile_ymax),
                )
            )

        tile_index = gpd.GeoDataFrame(tile_extents, crs = self.full_region.boundary.crs)
        return tile_index

    def generate_tile(self, index):

        tile_info = self.tile_index.loc[index]

        # minx, miny, maxx, maxy = self.tile_index.loc[0].geometry.bounds
        minx, miny, maxx, maxy = tile_info.geometry.bounds
        
        _, resx, _, _, _, resy =  self.full_region.mask.raster.GetGeoTransform()
        
        nx, ny = abs((maxx-minx)/resx), abs((maxy-miny)/resy)

        proj = self.full_region.boundary.crs.to_wkt()
        gt = minx, resx, 0, maxy, 0, resy
        # print(gt)
        new_mask = empty_dataset(
            int(nx), int(ny), proj, gt, 
            bands=1, gdal_type=gdal.GDT_Int16
        )
        
        
        gdal.Warp(new_mask, self.full_region.mask.raster)
        new_mask = Mask(new_mask)

        subregion = Region(self.tile_index.loc[[index]].reset_index(), new_mask)

        for name, ds in self.full_region.data.items():
            subregion.import_from_datasource(name, ds)

        return subregion
