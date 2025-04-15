#!/usr/bin/env python


import pytest

from temds import AOIMask
from temds import tileindex


def test_aoi_download():
  aoimask = AOIMask.AOIMask(root = "../working")
  aoimask._download()

def test_aoi_unzip():
  aoimask = AOIMask.AOIMask(root = "../working")
  aoimask._unzip()

def test_aoi_create_from_shapefiles():
  aoimask = AOIMask.AOIMask(root = "../working")
  aoimask.create_from_shapefiles()

def test_aoi_get_shapefile_bounds():
  aoimask = AOIMask.AOIMask(root = "../working")
  aoimask.load_from_vector('working/aoi_5km_buffer_6931/aoi_5km_buffer_6931.shp')
  bounds = aoimask.get_shapefile_bounds()
  assert bounds['minx'] == pytest.approx(-4602000.0)
  assert bounds['miny'] == pytest.approx(-3485000.0)
  assert bounds['maxx'] == pytest.approx(4366000.0)
  assert bounds['maxy'] == pytest.approx(4251000.0)

def test_aoi_rasterize():
  aoimask = AOIMask.AOIMask(root = "../working")
  aoimask.load_from_vector('../working/aoi_5km_buffer_6931/aoi_5km_buffer_6931.shp')
  aoimask.rasterize_AOI()

def test_aoi_load_raster():
  aoimask = AOIMask.AOIMask(root = "../working")
  aoimask.load_from_raster('../working/aoi_5km_buffer_6931.tiff')
  assert (2242, 1934) == aoimask.size()


def test_tile_engine_cut_tileset():
  tile_index = tileindex.TileIndex(root = "working")
  tile_index.cut_tileset(tile_index.calculate_tile_extents())

def test_tile_engine_remove_tiles():
  tile_index = tileindex.TileIndex(root="working")
  tile_index.remove_tiles()



#1982709