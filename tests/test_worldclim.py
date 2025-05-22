#!/usr/bin/env python

import pytest

import xarray


from temds.datasources import worldclim


def test_worldclim_init(worldclim_object):
  assert isinstance(worldclim_object, worldclim.WorldClim)
  assert isinstance(worldclim_object.dataset, xarray.Dataset)

  assert len(worldclim_object.dataset.data_vars) >= 7

  assert 'tmax' in worldclim_object.dataset.data_vars
  assert 'tmin' in worldclim_object.dataset.data_vars
  assert 'tavg' in worldclim_object.dataset.data_vars
  assert 'prec' in worldclim_object.dataset.data_vars
  assert 'srad' in worldclim_object.dataset.data_vars
  assert 'vapr' in worldclim_object.dataset.data_vars
  assert 'wind' in worldclim_object.dataset.data_vars



