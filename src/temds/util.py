#!/usr/bin/env python

import os
import pathlib
import errno
import subprocess

from osgeo import gdal

import importlib.metadata # for version lookup


def Version():
  '''Return a version string. First try to get it from git, otherwise use the
  version from the installed package.

  This way for a developer's repo the reported version is always up to date with
  the latest commit. But for an copy of the repo that doesn't have the git
  history, (e.g. pip installed version from a shallow checkout) it will still
  report a version - the version that was packaged up.

  Even with a pip editable install, the versioningit number doesn't seem to keep
  up with the commits unless you reinstall the package. So the subprocess
  approach is still better for a developer's repo where you might make a lot of
  commits between installations (pip install -e .)

  Strange that the command line versioningit tool does manage to keep up with
  commits, but the version available through importlib.metadata.version()
  doesn't....
  '''

  try:
    # Need to check current directory, save it, and then change to the 
    # directory of the module then run the git command, then change back.
    # Otherwise if the current directory is not in the repo, git will complain.
    currentDir = os.getcwd()
    os.chdir(os.path.dirname(__file__))
    __version__ = subprocess.check_output(['git', 'describe', '--tags']).strip().decode('utf-8')
    os.chdir(currentDir)
  except subprocess.CalledProcessError as e:
    print(f"Warning: Couldn't get version from git, using installed version. {e}")
    os.chdir(currentDir)
    # Return the version string of the installed software. Managed by a special
    # tool called versioningit which is driven by git tags.
    __version__ = importlib.metadata.version("temds")

  return f"{__version__}"


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