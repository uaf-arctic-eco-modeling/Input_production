#!/usr/bin/env python

import numpy as np
from osgeo import gdal

import AOIMask

TILE_SIZE_X = 100
TILE_SIZE_Y = 100


class TileEngine(object):

  def __init__(self):
    print ("Instatitating a TileSet...")

  def calculate_tile_gridsize(self):
    aoimask = AOIMask.AOIMask()
    aoimask.load_from_raster('working/aoi_5km_buffer_6931.tiff')

    maskX, maskY = aoimask.size()

    N_TILES_X = int(maskX / TILE_SIZE_X)
    N_TILES_Y = int(maskY / TILE_SIZE_Y)

    if maskX % TILE_SIZE_X > 0:
      N_TILES_X += 1

    if maskX % TILE_SIZE_Y > 0:
      N_TILES_Y += 1

    return N_TILES_X, N_TILES_Y


  def calculate_tile_extents(self):
    '''
    Chop a raster up into tiles.
    Returns list of tile extent dictionaries. Each dict will have x, y, minx
    and max (projection coords) and H and V indices in the tileset. And the
    resolution.
    '''

    aoimask = AOIMask.AOIMask()
    aoimask.load_from_raster('working/aoi_5km_buffer_6931.tiff')
    
    maskX, maskY = aoimask.size()

    aoi_extents = aoimask.extents()

    aoiGT = aoimask.geoTransform()

    N_tiles_X, N_tiles_Y = self.calculate_tile_gridsize()

    tile_extents = []

    for h in range(N_tiles_X):
      for v in range(N_tiles_Y):

        tile_xmin = aoi_extents['minx'] + TILE_SIZE_X * h * aoiGT[1]
        if (h+1) == len(range(N_tiles_X)):
          tile_xmax = tile_xmin + (maskX % TILE_SIZE_X) * aoiGT[1]
        else:
          tile_xmax = tile_xmin + TILE_SIZE_X * aoiGT[1]

        tile_pixelXsize = aoiGT[1]
        tile_pixelYsize = aoiGT[5]

        # Origin LOWER LEFT
        tile_ymin = aoi_extents['miny'] + tile_pixelYsize * maskY \
                    + TILE_SIZE_Y * v * tile_pixelYsize * -1
        if (v+1) == len(range(N_tiles_Y)):
          tile_ymax = tile_ymin + (maskY % TILE_SIZE_Y) * tile_pixelYsize * -1
        else:
          tile_ymax = tile_ymin + TILE_SIZE_Y * tile_pixelYsize * -1 

        # # Origin UPPER LEFT 
        # tile_ymin = aoi_extents['miny'] + TILE_SIZE_Y * v * aoiGT[5]
        # if (v+1) == len(range(N_tiles_Y)):
        #   tile_ymax = tile_ymin + (maskY % TILE_SIZE_Y) * aoiGT[5]
        # else:
        #   tile_ymax = tile_ymin + TILE_SIZE_Y * aoiGT[5]

        tile_extents.append(dict(hidx=h, vidx=v, 
                                 xmin=tile_xmin, xmax=tile_xmax, 
                                 ymin=tile_ymin, ymax=tile_ymax,
                                 xrez=tile_pixelXsize, yrez=tile_pixelYsize))

    return tile_extents    

  def cut_tileset(self, tile_extents):
    '''Given a list of tile extents, call gdal warp and actually crop out
    the tile from the raster.'''

    for tile in tile_extents:

      warpOptions = {
        'format': 'VRT',
        'srcSRS': 'EPSG:6931',
        'dstSRS': 'EPSG:6931',
        'xRes': tile['xrez'],
        'yRes': tile['yrez'],
        #'outputType': '',
        'outputBounds': [tile['xmin'], tile['ymin'], tile['xmax'], tile['ymax']],
        #'resampleAlg': '',
      }

      # Put it in a temporary dataset
      ds = gdal.Warp('', 'working/aoi_5km_buffer_6931.tiff', **warpOptions)
      #print(f"H{tile['hidx']:02d}_V{tile['vidx']:02d}:   {np.count_nonzero(ds.ReadAsArray())} of {ds.RasterXSize* ds.RasterYSize}")

  def register_tileset():
    '''Inspect a file hirearchy'''
    pass