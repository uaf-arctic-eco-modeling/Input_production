#!/usr/bin/env python

import os
import pathlib
import errno

from osgeo import gdal

'''
'''

def gdalGeoTransformHelp():
  '''Print some handy info.'''

  print('''
GT(0) x-coordinate of the upper-left corner of the upper-left pixel.
GT(1) w-e pixel resolution / pixel width.
GT(2) row rotation (typically zero).
GT(3) y-coordinate of the upper-left corner of the upper-left pixel.
GT(4) column rotation (typically zero).
GT(5) n-s pixel resolution / pixel height (negative value for a north-up image).
https://gdal.org/en/stable/tutorials/geotransforms_tut.html
''')

def mkdir_p(path):
  '''Provides similar functionality to bash mkdir -p'''
  try:
     os.makedirs(path)
  except OSError as exc:  # Python >2.5
    if exc.errno == errno.EEXIST and os.path.isdir(path):
      pass
    else:
      raise

def getRasterExtents(raster):
  '''
  Hackish approach to computing raster extents...
  Not sure how robust the type checking approach is...
  '''
  if type(raster) is str or type(raster) is pathlib.PosixPath:
    ds = gdal.Open(raster, gdal.gdalconst.GA_ReadOnly)
  else:
    ds = raster # assume that raster is an osgeo.gdal.Dataset

  geoTransform = ds.GetGeoTransform()
  minx = geoTransform[0]
  miny = geoTransform[3]
  maxx = minx + geoTransform[1] * ds.RasterXSize
  maxy = miny + geoTransform[5] * ds.RasterYSize

  return [minx, miny, maxx, maxy]
