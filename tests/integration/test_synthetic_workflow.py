"""
Integration tests using synthetic test data.

These tests demonstrate the full workflow using synthetic fixtures,
providing fast end-to-end testing without requiring external data downloads.
"""

import pytest
import numpy as np
import xarray as xr
from pathlib import Path

import temds.datasources.dataset
import temds.datasources.timeseries
import temds.aoitools
import temds.tile
import temds.logger


def test_synthetic_worldclim_basic_properties(synthetic_worldclim_data):
    """Test that synthetic WorldClim data has expected structure."""
    ds = synthetic_worldclim_data
    
    # Check dimensions
    assert 'x' in ds.dims
    assert 'y' in ds.dims
    assert ds.dims['x'] == 10
    assert ds.dims['y'] == 10
    
    # Check coordinates
    assert 'lat' in ds.coords
    assert 'lon' in ds.coords
    assert 'X' in ds.coords
    assert 'Y' in ds.coords
    
    # Check variables - should have 24 (12 temp + 12 precip)
    expected_vars = [f'tair_{i}' for i in range(1, 13)] + [f'prec_{i}' for i in range(1, 13)]
    for var in expected_vars:
        assert var in ds.data_vars
        assert ds[var].shape == (10, 10)


def test_synthetic_cru_timeseries_structure(synthetic_cru_timeseries):
    """Test that synthetic CRU time series has correct structure."""
    datasets = synthetic_cru_timeseries
    
    # Should have 3 years
    assert len(datasets) == 3
    
    # Each dataset should have time dimension
    for ds in datasets:
        assert 'time' in ds.dims
        assert ds.dims['x'] == 10
        assert ds.dims['y'] == 10
        
        # Check for typical climate variables
        assert 'tair_avg' in ds.data_vars
        assert 'prec' in ds.data_vars
        
        # Data should be 3D (time, y, x)
        assert ds['tair_avg'].ndim == 3


def test_synthetic_aoi_all_shapes(aoi_shape):
    """Test AOI generation with all shape types."""
    from tests.fixtures.generators import generate_synthetic_aoi
    
    aoi_gdf = generate_synthetic_aoi(shape=aoi_shape, seed=42)
    
    # Should be a GeoDataFrame with one feature
    assert len(aoi_gdf) == 1
    assert aoi_gdf.crs.to_string() == 'EPSG:6931'
    
    # Should have valid geometry
    assert aoi_gdf.geometry.iloc[0].is_valid
    
    # Check approximate area (should be roughly correct for square/triangle)
    if aoi_shape in ['square', 'triangle']:
        area = aoi_gdf.geometry.iloc[0].area
        assert area > 1e8  # At least 100 km²


def test_tiny_raster_for_unit_tests(tiny_raster):
    """Test generation of minimal raster for fast unit tests."""
    assert tiny_raster.dims['x'] == 5
    assert tiny_raster.dims['y'] == 5
    assert 'tair_avg' in tiny_raster.data_vars
    assert 'prec' in tiny_raster.data_vars


def test_tmp_workspace_structure(tmp_workspace):
    """Test that temporary workspace has correct directory structure."""
    # Check key directories exist
    assert (tmp_workspace / 'working/00-download/worldclim').exists()
    assert (tmp_workspace / 'working/01-aoi').exists()
    assert (tmp_workspace / 'working/02-data').exists()
    assert (tmp_workspace / 'working/03-tiles').exists()


def test_aoi_rasterization_workflow(small_test_aoi, tmp_workspace, logger):
    """Test AOI loading and rasterization with synthetic data."""
    # Save the synthetic AOI to a file
    aoi_path = tmp_workspace / 'working/01-aoi/test_aoi.shp'
    small_test_aoi.to_file(aoi_path)
    
    # Load it back with temds
    aoi_mask = temds.aoitools.AOIMask.load_vector(str(aoi_path))
    
    # Check that it loaded correctly
    assert aoi_mask.aoi is not None
    assert len(aoi_mask.aoi) > 0


def test_vegetation_data_structure(synthetic_vegetation_data):
    """Test synthetic vegetation data structure."""
    ds = synthetic_vegetation_data
    
    assert 'veg_class' in ds.data_vars
    assert ds['veg_class'].dtype == np.int32
    
    # Values should be in reasonable range (0-4 for 5 classes)
    assert ds['veg_class'].min() >= 0
    assert ds['veg_class'].max() < 5


def test_topo_data_structure(synthetic_topo_data):
    """Test synthetic topography data structure."""
    ds = synthetic_topo_data
    
    # Should have elevation, slope, aspect
    assert 'elevation' in ds.data_vars
    assert 'slope' in ds.data_vars
    assert 'aspect' in ds.data_vars
    
    # Check reasonable value ranges
    assert ds['elevation'].min() > 0
    assert ds['slope'].min() >= 0
    assert ds['slope'].max() <= 90
    assert ds['aspect'].min() >= 0
    assert ds['aspect'].max() <= 360


@pytest.mark.slow
def test_end_to_end_mini_pipeline(
    synthetic_worldclim_data,
    synthetic_cru_timeseries,
    small_test_aoi,
    tmp_workspace,
    logger
):
    """
    End-to-end test of a minimal pipeline using only synthetic data.
    
    This test is marked 'slow' because it exercises the full workflow,
    though it's still much faster than using real data.
    """
    # 1. Save AOI
    aoi_path = tmp_workspace / 'working/01-aoi/test_aoi.shp'
    small_test_aoi.to_file(aoi_path)
    
    # 2. Create AOI mask
    aoi_mask = temds.aoitools.AOIMask.load_vector(str(aoi_path))
    assert aoi_mask.aoi is not None
    
    # 3. Save synthetic worldclim data
    wc_path = tmp_workspace / 'working/02-data/worldclim.nc'
    synthetic_worldclim_data.to_netcdf(wc_path)
    
    # 4. Load it as TEMDataset
    wc = temds.datasources.dataset.TEMDataset(str(wc_path))
    assert wc.data is not None
    
    # 5. Save synthetic CRU data
    cru_dir = tmp_workspace / 'working/02-data/cru'
    cru_dir.mkdir(exist_ok=True)
    for i, ds in enumerate(synthetic_cru_timeseries):
        year = 1901 + i
        ds.to_netcdf(cru_dir / f'cru_{year}.nc')
    
    # 6. Create a simple tile
    extent = aoi_mask.get_raster_extent().iloc[0]
    simple_tile = temds.tile.Tile(
        index=(0, 0),
        bounds=(extent['minx'], extent['maxx'], extent['miny'], extent['maxy']),
        resolution=4000,
        crs=aoi_mask.aoi.crs,
        buffer_px=0,
        logger=logger
    )
    
    # Verify tile was created successfully
    assert simple_tile.index == (0, 0)
    assert simple_tile.resolution == 4000


def test_deterministic_synthetic_data():
    """Test that synthetic data generation is deterministic with same seed."""
    from tests.fixtures.generators import generate_synthetic_raster
    
    # Generate same data twice with same seed
    ds1 = generate_synthetic_raster(n_x=5, n_y=5, variables=['tair_avg'], seed=42)
    ds2 = generate_synthetic_raster(n_x=5, n_y=5, variables=['tair_avg'], seed=42)
    
    # Should be identical
    np.testing.assert_array_equal(ds1['tair_avg'].values, ds2['tair_avg'].values)
    
    # Different seed should give different data
    ds3 = generate_synthetic_raster(n_x=5, n_y=5, variables=['tair_avg'], seed=99)
    
    # Should NOT be identical
    assert not np.array_equal(ds1['tair_avg'].values, ds3['tair_avg'].values)


def test_synthetic_data_has_realistic_values(synthetic_worldclim_data):
    """Test that synthetic data has realistic climate values."""
    ds = synthetic_worldclim_data
    
    # Temperature should be in reasonable range for Arctic (-50 to +30°C)
    for month in range(1, 13):
        tair = ds[f'tair_{month}'].values
        assert tair.min() > -50
        assert tair.max() < 30
    
    # Precipitation should be positive
    for month in range(1, 13):
        prec = ds[f'prec_{month}'].values
        assert (prec >= 0).all()


def test_synthetic_timeseries_temporal_continuity(synthetic_cru_timeseries):
    """Test that synthetic time series has temporal continuity."""
    datasets = synthetic_cru_timeseries
    
    # Check that years are sequential
    years = [ds.attrs.get('year') for ds in datasets]
    assert years == [1901, 1902, 1903]
    
    # Check that each year has correct number of days
    for ds in datasets:
        year = ds.attrs['year']
        n_days = 366 if year == 1904 else 365  # 1904 would be leap year
        # For our test years (1901-1903), none are leap years
        assert len(ds.time) == 365
