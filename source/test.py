#!/usr/bin/env python

# Mess around with this as a driver for active development...

import mask


def test_download_AOI_maps():
  mask.download_AOI_maps()

def test_create_AOI_shapefiles():
  mask.create_AOI_shapefiles('working/download/mask/geoBoundariesCGAZ_ADM1/geoBoundariesCGAZ_ADM1.shp',
               'working/download/mask/Ecoregions2017/Ecoregions2017.shp')

def test_unzip_AOI_maps():
  mask.unzip_AOI_maps()

def test_get_AOI_extents():
  print(mask.get_AOI_extents('working/aoi_5km_buffer_6931/aoi_5km_buffer_6931.shp'))

def test_rasterize_AOI():
  mask.rasterize_AOI()

if __name__ == '__main__':

  #test_download_AOI_maps()
  #test_create_AOI_shapefiles()
  test_unzip_AOI_maps()

  test_get_AOI_extents()
  test_rasterize_AOI()