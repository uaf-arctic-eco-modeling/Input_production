#!/usr/bin/env python

# pytest -x --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb /path/to/test.py

import pytest

from temds import aoitools
from temds import tileindex


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

def test_aoi_unzip():
  aoimask = aoitools.AOIMask(root = "working")
  aoimask._unzip()

def test_aoi_create_from_shapefiles():
  aoimask = aoitools.AOIMask(root = "working")
  aoimask.create_from_shapefiles()

def test_aoi_get_shapefile_bounds():
  aoimask = aoitools.AOIMask(root = "working")
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

def test_aoi_load_raster():
  aoimask = aoitools.AOIMask(root = "working")
  aoimask.load_from_raster('working/01-aoi/aoi_5km_buffer_6931.tiff')
  assert (2242, 1934) == aoimask.size()


def test_tile_engine_cut_tileset():
  tile_index = tileindex.TileIndex(root = "working")
  tile_index.cut_tileset(tile_index.calculate_tile_extents())

def test_tile_engine_remove_tiles():
  tile_index = tileindex.TileIndex(root="working")
  tile_index.remove_tiles()

