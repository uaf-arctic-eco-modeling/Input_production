#!/usr/bin/env python

#
# Example for running the tests in a "development" mode - i.e. working on 
# developing the tests:
#     $ pytest tests/test_tile.py -x --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb
#

import pathlib
import pytest
import geopandas as gpd
import numpy as np
import xarray as xr

import temds
from temds import tile

# Import test fixtures and generators
from tests.fixtures.generators import (
    generate_synthetic_aoi,
    generate_synthetic_raster,
    generate_synthetic_timeseries,
    generate_synthetic_vegetation,
    generate_synthetic_topo,
)
from tests.fixtures.mocks import (
    create_tmp_workspace,
    mock_worldclim_download,
    mock_crujra_files,
) 

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


# =============================================================================
# NEW SYNTHETIC TEST FIXTURES
# These are fast, require no external data, and are the preferred fixtures
# for new tests. The fixtures above are preserved for backward compatibility.
# =============================================================================

@pytest.fixture(scope='session')
def synthetic_worldclim_data():
    """Generate synthetic WorldClim-like data once per test session."""
    variables = [
        'tair_1', 'tair_2', 'tair_3', 'tair_4', 'tair_5', 'tair_6',
        'tair_7', 'tair_8', 'tair_9', 'tair_10', 'tair_11', 'tair_12',
        'prec_1', 'prec_2', 'prec_3', 'prec_4', 'prec_5', 'prec_6',
        'prec_7', 'prec_8', 'prec_9', 'prec_10', 'prec_11', 'prec_12'
    ]
    return generate_synthetic_raster(
        n_x=10, n_y=10, 
        variables=variables,
        seed=42
    )


@pytest.fixture(scope='session')
def synthetic_cru_timeseries():
    """Generate synthetic CRU-JRA time series for 3 years."""
    return generate_synthetic_timeseries(
        start_year=1901,
        n_years=3,
        n_x=10,
        n_y=10,
        seed=42
    )


@pytest.fixture(scope='session')
def synthetic_vegetation_data():
    """Generate synthetic vegetation classification data."""
    return generate_synthetic_vegetation(n_x=10, n_y=10, seed=42)


@pytest.fixture(scope='session')
def synthetic_topo_data():
    """Generate synthetic topography data."""
    return generate_synthetic_topo(n_x=10, n_y=10, seed=42)


@pytest.fixture(params=['square', 'triangle', 'polygon'])
def aoi_shape(request):
    """Parameterized fixture for testing different AOI shapes."""
    return request.param


@pytest.fixture
def synthetic_aoi(aoi_shape):
    """Generate synthetic AOI with parameterized shape."""
    return generate_synthetic_aoi(shape=aoi_shape, seed=42)


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create temporary workspace with standard directory structure."""
    return create_tmp_workspace(tmp_path)


@pytest.fixture
def small_test_aoi():
    """Simple square AOI for basic testing."""
    return generate_synthetic_aoi(shape='square', size=20000.0, seed=42)


@pytest.fixture
def tiny_raster():
    """Minimal 5x5 raster for fast unit tests."""
    return generate_synthetic_raster(
        n_x=5, n_y=5,
        variables=['tair_avg', 'prec'],
        seed=42
    )


@pytest.fixture
def logger():
    """Standard test logger."""
    return temds.logger.Logger([], temds.logger.DEBUG)


# =============================================================================
# PARAMETERIZED FIXTURES FOR COMPREHENSIVE TESTING
# =============================================================================

@pytest.fixture(params=[5, 10, 20])
def raster_sizes(request):
    """Test with different raster sizes."""
    return request.param


@pytest.fixture
def synthetic_raster(raster_sizes):
    """Synthetic raster with parameterized size."""
    return generate_synthetic_raster(
        n_x=raster_sizes,
        n_y=raster_sizes,
        seed=42
    )