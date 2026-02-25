#!/usr/bin/env python

from turtle import pd
import pytest


import temds.datasources
from temds.datasources.dataset import TEMDataset



def test_topo_huh(small_toolik_aoimask):
  '''Test topography creation from a small AOI mask.'''
  topo = temds.datasources.dataset.TEMDataset.from_topo(
    data_path='working/00-download/topo',
    extent_raster=pytest.SMALL_TOOLIK_RASTER_AOI,
    download=False
  )

  print(f'{topo.extent}')
  print(f'{topo.dataset.rio.bounds()}')

  print(f'{small_toolik_aoimask.get_vector_bounds().squeeze()}')
  print(f'{small_toolik_aoimask.get_raster_extent().squeeze()}')
  print(f'{small_toolik_aoimask.get_resolution_aligned_bounds()}')



  G = pd.concat([
              small_toolik_aoimask.get_resolution_aligned_bounds(),           # flooring/ceil the vector bounds
              small_toolik_aoimask.get_vector_bounds().squeeze(),             # geo pandas bounds
              small_toolik_aoimask.get_raster_extent().squeeze(),             # geopandas bounds -> rez aligned -> gdal.Rasterize -> gdal geotransform
              pd.Series(topo.extent, index=['minx','miny','maxx','maxy']),    # rasterio bounds
            ],
             keys= ['aoi_rab','aoi_vb','aoi_re','topo_e'], 
             axis=1).transpose()
  H = G['maxx'] - G['minx']

  assert topo is not None
  assert topo.extent == small_toolik_aoimask.get_vector_bounds()


def test_topo_init():
  '''Full arctic topo creation from a raster extent. Slow (~2min)'''
  assert  1 == 0
  topo = temds.datasources.dataset.TEMDataset.from_topo(
    data_path = 'working/00-download/topo',
    extent_raster = 'working/01-aoi/aoi-5km-buffer-6931.tif',
    download = False
  )

  assert topo is not None
  assert topo.extent == (6931, 6931, 6931, 6931)


def test_topo_download():
  raise NotImplementedError("Need to implement a test for downloading topo data")

