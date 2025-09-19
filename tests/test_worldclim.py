#!/usr/bin/env python

import pytest

import xarray


import temds


def test_worldclim_init(worldclim_object):
  assert isinstance(worldclim_object, temds.datasources.dataset.TEMDataset)
  assert isinstance(worldclim_object.dataset, xarray.Dataset)

  assert len(worldclim_object.dataset.data_vars) >= 7
  
  # Get a list of all the variable abbreviations that exist for the worldclim
  var_names = [cv.abbr for cv in temds.climate_variables.list_for('worldclim')]

  # check that all of them are present in the object's dataset.
  for v in var_names:
    assert v in worldclim_object.dataset.data_vars
  



