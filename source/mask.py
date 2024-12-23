#!/usr/bin/env python

import pathlib
import requests
import zipfile
import numpy as np
import subprocess
import geopandas as gpd

import util









def get_AOI_extents(shapefile):
  '''
  Opens a shapefile, reads the extents, does some rounding and padding
  and returns a tuple: (minx, miny, maxx, maxy)
  '''

  RES = 4000 # meters

  sf = gpd.read_file(shapefile)
  extents = sf.geometry.bounds

  # Funky business to get nice clean numbers for the bounds that are big enough.
  # Extents is a DataFrame, so we can proccess it en masse.
  # numbers start like this:
  #
  #                minx          miny          maxx          maxy
  #     0 -4.602688e+06 -3.485976e+06  4.363719e+06  4.247969e+06
  #
  # and end like this:
  #
  #             minx       miny       maxx       maxy
  #     0 -4602000.0 -3485000.0  4364000.0  4248000.0
  #
  # actually not sure this works as intended for negative numbers??

  extents = np.ceil((extents/1000))*1000

  # Fiddle with extents to be multiplier of RESOLUTION
  max_x = extents['maxx'] + (RES - (extents['maxx'] - extents['minx']) % RES)
  max_y = extents['maxy'] + (RES - (extents['maxy'] - extents['miny']) % RES)

  # The above data structures are all pandas.DataFrames so you gotta get just
  # the values out.
  return (extents['minx'].values[0], extents['miny'].values[0], max_x.values[0], max_y.values[0])


def rasterize_AOI():

  layer_name = 'aoi_5km_buffer_6931'
  RES = str(4000)
  target_extents = get_AOI_extents('working/aoi_5km_buffer_6931/aoi_5km_buffer_6931.shp')

  target_extents = [str(int(x)) for x in target_extents]
  args = ['gdal_rasterize',
          '-l', layer_name,
          '-burn', str(1),
          '-tr', RES, RES,
          '-a_nodata', str(0),
          '-te', *(target_extents),
          '-ot', 'Int16',
          '-of', 'GTiff',
          'working/aoi_5km_buffer_6931/aoi_5km_buffer_6931.shp',
          'working/aoi_5km_buffer_6931.tiff'
          ]
  print(args)
  subprocess.run(args)



