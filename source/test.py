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



if __name__ == '__main__':

  #test_download_AOI_maps()
  #test_create_AOI_shapefiles()
  test_unzip_AOI_maps()

