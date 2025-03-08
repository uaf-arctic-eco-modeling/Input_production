#!/usr/bin/env python


from xarray import Dataset

from temds import crujra

def test_load_from_raw():
  aoi_extent = (-180.0, 180.0, 44.930151, 84.223125)
  _1901 = crujra.CRU_JRA_daily(
    1901, 'data/raw/', _vars=['tmax','dswrf'], aoi_extent = aoi_extent
  )
  # _1901.load_from_raw('data/raw/', aoi_extent)
  _1901.save('data/test_from_raw.nc') # use later


  assert not _1901.dataset is None
  assert type(_1901.dataset) is Dataset


def test_load():
  _1901 = crujra.CRU_JRA_daily(
    1901, 'data/test_from_raw.nc', verbose=True, _vars=['tmax','dswrf']
  )
  # _1901.load()
  assert not _1901.dataset is None
  assert type(_1901.dataset) is Dataset
 
  
def test_aoi_correct():
  _1901 = crujra.CRU_JRA_daily(
    1901, 'data/test_from_raw.nc', verbose=True, _vars=['tmax','dswrf']
  )
  assert 44.930151 < float(_1901.dataset.lat.data[0])
  assert float(_1901.dataset.lat.data[-1]) < 84.223125 
  assert -180.0 < float(_1901.dataset.lon.data[0])
  assert float(_1901.dataset.lon.data[-1]) < 180.0 



