#!/usr/bin/env python

import pytest
from pathlib import Path

import geopandas as gpd
import numpy as np

import temds

from temds.datasources import timeseries, worldclim
from temds.datasources import crujra
from temds import tile 


@pytest.fixture(scope='module')
def worldclim_object():
  wc = temds.datasources.dataset.TEMDataset('working/02-arctic/worldclim/worldclim-arctic.nc')
  return wc

@pytest.fixture(scope='module')
def micro_list_cru():
 
  START_YR = 1990
  END_YR = 1994

  annual_list = []
  file_list = sorted(list(Path('working/02-arctic/cru-jra-25/').glob('*.nc')))
  for cru_file in file_list:
      year = int(cru_file.name.split('.')[-4])
      if year >= START_YR and year <= END_YR:
          temp = temds.datasources.dataset.YearlyDataset(year, cru_file, verbose=False, force_aoi_to='tmax', crs='EPSG:4326', aoi_nodata=np.nan)
          annual_list.append(temp)
  return annual_list


@pytest.fixture(scope='module')
def cru_arctic_timeseries_micro(micro_list_cru):
  # This is a short timeseries of the CRU data
  # It is not the full dataset, 'cuz that is so slow to load...
  cru_arctic_ts = timeseries.YearlyTimeSeries(micro_list_cru, logger=temds.logger.Logger([], temds.logger.INFO), in_memory=False)

  return cru_arctic_ts


@pytest.fixture(scope='module')
def basic_tile():
  HIDX = 0
  VIDX = 8
  tile_index = gpd.read_file('working/tile_index_annotated.shp')
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