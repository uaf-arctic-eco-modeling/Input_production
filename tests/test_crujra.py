#!/usr/bin/env python

import sys
import os
sys.path.append(os.path.abspath('../source/'))

import pytest
from xarray import Dataset

import crujra

def test_load_from_raw():
  aoi_extent = (-180.0, 180.0, 44.930151, 84.223125)
  _1901 = crujra.CRU_JRA_daily(1901, 'n/a', _vars=['tmax','dswrf'])
  _1901.load_from_raw('data/raw/', aoi_extent)
  _1901.save('data/test_from_raw.nc') # use later
  assert not _1901.dataset is None
  assert type(_1901.dataset) is Dataset

def test_load():
  _1901 = crujra.CRU_JRA_daily(1901, 'n/a', verbose=True, _vars=['tmax','dswrf'])
  _1901.load('data/test_from_raw.nc')
  assert not _1901.dataset is None
  assert type(_1901.dataset) is Dataset
 
  



