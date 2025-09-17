#!/usr/bin/env python

#
# Example for running the tests in a "development" mode - i.e. working on 
# developing the tests:
#     $ pytest tests/test_tile.py -x --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb
#

import pathlib
import pytest
import geopandas as gpd

import temds
from temds import tile 

def pytest_configure(config):
    '''Setup any global variables that should be shared across all tests.'''
    pytest.CRU_L1_FOLDER = 'working/02-arctic/cru-jra-standard/'
    pytest.WORLDCLIM_L1_FILE = 'working/02-arctic/worldclim/worldclim-arctic.nc'


@pytest.fixture(scope='module')
def worldclim_object():
  wc = temds.datasources.dataset.TEMDataset('working/02-arctic/worldclim/worldclim-arctic.nc')
  return wc


@pytest.fixture(scope="module")
def cru_arctic_timeseries_micro():
  '''This loads the Arctic files from the CRU JRA-25 dataset. There are
  "level 1" processed files: we have already uncompressed, cropped to the arctic,
  and saved as uncompressed netcdf files. Additionally, the variables have all been
   combined into a single file for each year.
  '''
  files = sorted(list(pathlib.Path(pytest.CRU_L1_FOLDER).glob('*.nc')))

  micro_arctic = temds.datasources.timeseries.YearlyTimeSeries(files[0:5], logger=temds.logger.Logger(), in_memory=False)

  return micro_arctic


@pytest.fixture(scope='module')
def basic_tile():
  HIDX = 0
  VIDX = 8
  tile_index = gpd.read_file('working/01-aoi/tile_index_annotated.shp')
  hdx = tile_index['H'] == HIDX
  vdx = tile_index['V'] == VIDX
  bounds = tile_index[vdx & hdx].bounds
  mytile = tile.Tile((HIDX,VIDX), bounds, 4000, tile_index.crs, buffer_px=20)

  return mytile

@pytest.fixture(scope='module')
def loaded_tile(basic_tile, worldclim_object, cru_arctic_timeseries_micro):
  basic_tile.import_and_normalize('worldclim', worldclim_object)
  basic_tile.import_and_normalize('crujra', cru_arctic_timeseries_micro)
  return basic_tile

@pytest.fixture(scope='module')
def downscaled_tile():
  '''Takes ~30s to load full timeseries.'''
  _tile = tile.Tile.tile_from_directory("working/04-downscaled-tiles/H00_V08/")
  return _tile