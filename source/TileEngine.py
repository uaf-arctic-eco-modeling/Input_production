#!/usr/bin/env python

import pathlib
import shutil
import glob
import numpy as np
from osgeo import gdal


import util
import AOIMask

TILE_SIZE_X = 100
TILE_SIZE_Y = 100


class TileEngine(object):

  def __init__(self, root):
    self.root = root

    self.aoimask = AOIMask.AOIMask(root=self.root)
    self.aoimask.load_from_raster(self.root + '/aoi_5km_buffer_6931.tiff')

  def remove_tiles(self):
    shutil.rmtree(self.root + "/tiles")
  

  def calculate_tile_gridsize(self):

    maskX, maskY = self.aoimask.size()

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

    
    maskX, maskY = self.aoimask.size()

    aoi_extents = self.aoimask.extents()

    aoiGT = self.aoimask.geoTransform()

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
      ds = gdal.Warp('', self.root+'/aoi_5km_buffer_6931.tiff', **warpOptions)

      if np.count_nonzero(ds.ReadAsArray()) < 1:
        print("Skip tile!")
      else:
        # get indices of non-zero data. Use theses to further trim down the
        # extents of the tiles.
        valid_y, valid_x = np.nonzero(ds.ReadAsArray())
        transOptions = {
          'format': 'VRT',
          # [left x, top_y, width, height]
          'srcWin': [valid_x.min(), valid_y.min(), 
                    valid_x.max()-valid_x.min()+1, valid_y.max()-valid_y.min()+1 ] 
        }

        print(f"cropping H{tile['hidx']} V{tile['vidx']}", transOptions)
        vrt = gdal.GetDriverByName('VRT')
        ds = gdal.Translate('', ds, **transOptions)

        outdir = pathlib.Path(self.root, 'tiles', f"H{tile['hidx']:02d}_V{tile['vidx']:02d}")
        util.mkdir_p(outdir)

        print(f"Writing to: {outdir}")
        out = gdal.GetDriverByName('GTiff')
        out.CreateCopy(pathlib.Path(outdir, "EPSG_6931.tiff"), ds)

        warpOpts = {'dstSRS':'EPSG:4326'}
        ds = gdal.Warp(pathlib.Path(outdir, "EPSG_4326.tiff"), ds, **warpOpts)


  def create_tile_index(self):
    opts = {
      'overwrite': True,
      'filenameFilter' : "*6931.tiff",

    }
    files = glob.glob(self.root + "/tiles/**/EPSG_6931.tiff")

    print(f"Found {len(files)} files to tile.")    
    dstPath = pathlib.Path(self.root + "tile_index.shp")

    gdal.TileIndex(dstPath, 
                   files,
                   **opts)
    if not dstPath.exists():
      raise RuntimeError(f"PROBLEM CREATING TILE INDEX: {dstPath}")
    

  def get_tile_index_total_area(self):
    files = glob.glob(self.root + "/tiles/**/EPSG_6931.tiff")
    total = 0
    for raster_file in files:
      ds = gdal.Open(raster_file,  gdal.gdalconst.GA_ReadOnly)
      total += ds.RasterXSize * ds.RasterYSize

    return total

  def register_tileset():
    '''use gdal.TileIndex()'''
    pass