#!/usr/bin/env python

import pytest
import xarray
import pyproj

from temds import tile
from temds.datasources import crujra
from temds import datasources 

def test_tile_crs(basic_tile):
  assert isinstance(basic_tile.crs, pyproj.crs.crs.CRS)
  assert basic_tile.crs.to_epsg() == 6931




def test_tile_init(basic_tile):
  assert isinstance(basic_tile, tile.Tile)
  assert basic_tile.index == (0, 8)
  assert basic_tile.extent['minx'].iloc[0] == pytest.approx(-4554000.0)
  assert basic_tile.extent['miny'].iloc[0] == pytest.approx(-285000.0)
  assert basic_tile.extent['maxx'].iloc[0] == pytest.approx(-4202000.0)
  assert basic_tile.extent['maxy'].iloc[0] == pytest.approx(115000.0)
  assert basic_tile.buffer_pixels == 20

  # Not sure how to check the crs ...it is a string in the tile object
  # so I can't check it against the crs of the tileindex without a bit of work
  # and maybe another library to convert the string to a crs object??

def test_tile_import_worldclim(basic_tile, worldclim_object):

  basic_tile.import_and_normalize('worldclim', worldclim_object)

  assert isinstance(basic_tile.data['worldclim'], datasources.dataset.TEMDataset)
  assert isinstance(basic_tile.data['worldclim'].dataset, xarray.Dataset)

  # Make sure that the worldclim data is bigger than the tile extents  
  tile_xsize = (basic_tile.extent['maxx'] - basic_tile.extent['minx']) / basic_tile.resolution
  tile_ysize = (basic_tile.extent['maxy'] - basic_tile.extent['miny']) / basic_tile.resolution
  assert basic_tile.data['worldclim'].dataset.x.size == pytest.approx(tile_xsize + 2*basic_tile.buffer_pixels)
  assert basic_tile.data['worldclim'].dataset.y.size == pytest.approx(tile_ysize + 2*basic_tile.buffer_pixels)



def test_tile_import_crujra(basic_tile, cru_arctic_timeseries_micro):

  basic_tile.import_and_normalize('crujra', cru_arctic_timeseries_micro)
  assert isinstance(basic_tile.data['crujra'], datasources.timeseries.YearlyTimeSeries)


# kinda sloooooow
def test_tile_loaded_datasets(loaded_tile):
  assert isinstance(loaded_tile.data['worldclim'].dataset, xarray.Dataset)
  assert isinstance(loaded_tile.data['crujra'], datasources.timeseries.YearlyTimeSeries)
  # CRS of all parties involved?
  # Check bounds of cru and world clim?

def test_tile_downscaled(downscaled_tile):

  assert isinstance(downscaled_tile.data['downscaled_cru'], datasources.timeseries.YearlyTimeSeries) # subclass


