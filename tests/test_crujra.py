#!/usr/bin/env python

import pathlib
import pytest
import temds.datasources


def test_found_cru_arctic_L1_files():
  '''
  Make sure we can find the "level 1" processed files. Helps for all the 
  remaining tests. Maybe will want to pass the directory as a parameter?
  '''
  i = sorted(list(pathlib.Path(pytest.CRU_L1_FOLDER).glob('*.nc')))

  assert len(i) > 0, f"No .nc files found in {pytest.CRU_L1_FOLDER}"


def test_load_cru_level1_file():
  '''Just make sure we can load up a few files...'''

  files = sorted(list(pathlib.Path(pytest.CRU_L1_FOLDER).glob('*.nc')))

  assert len(files) > 0, f"Can't find any files in {pytest.CRU_L1_FOLDER}"

  cru_arctic_2yrs = temds.datasources.timeseries.YearlyTimeSeries(files[0:2], logger=temds.logger.Logger(), in_memory=False)

  assert isinstance(cru_arctic_2yrs, temds.datasources.timeseries.YearlyTimeSeries)


def test_arctic_files(cru_arctic_timeseries_micro):
  '''Make sure the arctic files are actually arctic...'''
  assert (-180.0, 45.5, 180.0, 83.5) == cru_arctic_timeseries_micro.data[0].extent, "Extents don't match."
  assert 365 == len(cru_arctic_timeseries_micro.data[0].dataset.time), "Time dimension is not 365 days."
  assert 1901 == cru_arctic_timeseries_micro.data[0].year





