#!/usr/bin/env python

import pytest
import numpy as np

from temds.datasources import crujra
from temds.datasources import errors


# This is pretty slow and eats a lot of memory
@pytest.fixture(scope="module")
def _1901_raw():
  '''This loads raw files from the CRU JRA-25 dataset. It starts by uncompressing
  the files and then loads them to an xarray dataset. The extent is likely global
   as there are the "raw" files downloaded from the web... '''
  return crujra.AnnualDaily(
      1901, 
      'working/download/cru-jra-25/', 
      verbose=True, 
  )

@pytest.fixture(scope="module")
def _1901_arctic():
  '''This loads the Arctic files from the CRU JRA-25 dataset. There are
  "level 1" processed files: we have already uncompressed, cropped to the arctic,
  and saved as uncompressed netcdf files.'''
  return crujra.AnnualDaily(
      1901, 
      "working/02-arctic/cru-jra-25/crujra.arctic.v2.5.5d.1901.365d.noc.nc",
      verbose=True,
      force_aoi_to='tmax', aoi_nodata=np.nan
  )


# This one is pretty slow ......
def test_load_from_raw(_1901_raw):
  assert _1901_raw.year == 1901
  assert _1901_raw.dataset.time.size == 365


def test_arctic_file_extents(_1901_arctic):
  assert 44.930151 < float(_1901_arctic.dataset.lat.data[0])
  assert float(_1901_arctic.dataset.lat.data[-1]) < 84.223125 
  assert -180.0 < float(_1901_arctic.dataset.lon.data[0])
  assert float(_1901_arctic.dataset.lon.data[-1]) < 180.0 



def test_load_file(_1901_arctic):
  assert _1901_arctic.year == 1901
  assert _1901_arctic.dataset.time.size == 365

  assert 'tmin' in _1901_arctic.dataset.data_vars
  assert 'tmax' in _1901_arctic.dataset.data_vars
  assert 'tmp' in _1901_arctic.dataset.data_vars
  assert 'pre' in _1901_arctic.dataset.data_vars
  assert 'dswrf' in _1901_arctic.dataset.data_vars
  assert 'ugrd' in _1901_arctic.dataset.data_vars
  assert 'vgrd' in _1901_arctic.dataset.data_vars
  assert 'spfh' in _1901_arctic.dataset.data_vars
  assert 'pres' in _1901_arctic.dataset.data_vars
  

def test_bad_file():
  with pytest.raises(IOError):
    crujra.AnnualDaily(
        1901, 
        "a/bad/file/path/crujra.arctic.v2.5.5d.1901.365d.noc.nc",
        verbose=True,
        force_aoi_to='tmax', aoi_nodata=np.nan
    )

def test_file_year_mismatch():
  with pytest.raises(errors.AnnualDailyYearMismatchError):
    temp = crujra.AnnualDaily(
        2023, 
        "working/02-arctic/cru-jra-25/crujra.arctic.v2.5.5d.1901.365d.noc.nc",
        verbose=True,
        force_aoi_to='tmax', aoi_nodata=np.nan
    )

    print(temp.year)
    print(temp.dataset.time.size)



