#!/usr/bin/env python

# pytest -x --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb /path/to/test.py

import pytest
import requests
from pathlib import Path


from temds import aoitools


@pytest.mark.parametrize(
  "url",
  [
    aoitools.AOIMask.politic_map_url,
    aoitools.AOIMask.eco_map_url,
  ],
)
def test_aoi_political_eco_maps_available(url):
  headers = {"Range": "bytes=0-1023"}

  with requests.get(url, headers=headers, stream=True, timeout=(5, 30)) as response:
    assert response.status_code in (200, 206), f"Unexpected status code {response.status_code} for {url}"
    first_chunk = next(response.iter_content(chunk_size=256), b"")
    assert first_chunk, f"No bytes received when starting download from {url}"

def test_aoi_raw_materials_available():
  '''Make sure that the files have been downloaded to working/00-download/ and that they are not empty.'''
  political_zip = Path("working/00-download/mask") / aoitools.AOIMask.politic_map_fname
  eco_zip = Path("working/00-download/mask") / aoitools.AOIMask.eco_map_fname 
  assert political_zip.exists() and political_zip.stat().st_size > 0, f"Political map zip file {political_zip} is missing or empty."
  assert eco_zip.exists() and eco_zip.stat().st_size > 0, f"Eco map zip file {eco_zip} is missing or empty."


def test_aoi_create_from_shapefiles():
  aoimask = aoitools.AOIMask()
  aoimask.create_from_shapefiles()

def test_aoi_get_shapefile_bounds():
  aoimask = aoitools.AOIMask()
  aoimask.load_from_vector('working/01-aoi/aoi_5km_buffer_6931/aoi_5km_buffer_6931.shp')
  bounds = aoimask.get_shapefile_bounds()
  assert bounds['minx'] == pytest.approx(-4602000.0)
  assert bounds['miny'] == pytest.approx(-3485000.0)
  assert bounds['maxx'] == pytest.approx(4366000.0)
  assert bounds['maxy'] == pytest.approx(4251000.0)

def test_aoi_rasterize():
  aoimask = aoitools.AOIMask(root = "working")
  aoimask.load_from_vector('working/01-aoi/aoi_5km_buffer_6931/aoi_5km_buffer_6931.shp')
  aoimask.rasterize_AOI()

def test_aoi_load_full_arctic_raster():

  aoi_raster_path = Path('working/01-aoi/full-arctic/full-arctic_6931_4000m.tiff')
  assert aoi_raster_path.exists() and aoi_raster_path.stat().st_size > 0, f"AOI raster file {aoi_raster_path} is missing or empty."

  aoimask = aoitools.AOIMask.load_raster(aoi_raster_path, mask_value=0)
  
  expected_extent = dict(minx=-4602000.0, miny=-3485000.0, maxx=4366000.0, maxy=4251000.0)
  for key, value in expected_extent.items():
    assert aoimask.get_raster_extent().iloc[0][key] == pytest.approx(value), f"Raster bound {key} does not match expected value {value}. Got {aoimask.get_raster_extent().iloc[0][key]} instead."
    assert aoimask.get_vector_bounds().iloc[0][key] == pytest.approx(value), f"Vector bound {key} does not match expected value {value}. Got {aoimask.get_vector_bounds().iloc[0][key]} instead." 


def test_tile_engine_cut_tileset():
  tile_index = aoitools.TileIndex(root = "working")
  tile_index.cut_tileset(tile_index.calculate_tile_extents())

def test_tile_engine_remove_tiles():
  tile_index = aoitools.TileIndex(root="working")
  tile_index.remove_tiles()

