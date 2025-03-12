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

def buffer_extent(extent, buffer, digits=6):
    """ 
    This adds a buffer to the passed in extents. Works in degrees.
    
    parameters
    ----------
    extent: list like
        extent in [minx,maxx,miny,maxy] order
        assumes coords are in degrees
    buffer: float
        buffer in degrees
    digits: int, default 6
        number of digits to pass to round

    returns
    -------
    tuple:
        (minx,maxx,miny,maxy) in degrees
    """
    minx = round(max(extent[0] - buffer, -180.0), 6)
    maxx = round(min(extent[1] + buffer,  180.0), 6)
    
    miny = round(max(extent[2] - buffer, -90.0), 6)
    maxy = round(min(extent[3] + buffer,  90.0), 6)

    
    return (minx, maxx, miny, maxy)