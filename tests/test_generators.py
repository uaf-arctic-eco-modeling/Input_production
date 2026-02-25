"""
Unit tests for synthetic test data generators.

These tests verify that the generator functions produce valid,
deterministic synthetic data without requiring external data sources.
"""

import pytest
import numpy as np
import xarray as xr
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon

from tests.fixtures.generators import (
    generate_synthetic_aoi,
    generate_synthetic_raster,
    generate_synthetic_timeseries,
    generate_synthetic_vegetation,
    generate_synthetic_topo,
)


class TestSyntheticAOI:
    """Tests for AOI generation."""
    
    def test_square_aoi(self):
        """Test generation of square AOI."""
        aoi = generate_synthetic_aoi(shape='square', seed=42)
        
        assert isinstance(aoi, gpd.GeoDataFrame)
        assert len(aoi) == 1
        assert isinstance(aoi.geometry.iloc[0], Polygon)
        assert aoi.crs.to_string() == 'EPSG:6931'
    
    def test_triangle_aoi(self):
        """Test generation of triangular AOI."""
        aoi = generate_synthetic_aoi(shape='triangle', seed=42)
        
        assert isinstance(aoi.geometry.iloc[0], Polygon)
        # Triangle should have 4 coordinates (3 vertices + closing point)
        assert len(aoi.geometry.iloc[0].exterior.coords) == 4
    
    def test_polygon_aoi(self):
        """Test generation of irregular polygon AOI."""
        aoi = generate_synthetic_aoi(shape='polygon', seed=42)
        
        assert isinstance(aoi.geometry.iloc[0], Polygon)
        # Should have 6-8 vertices plus closing point
        n_coords = len(aoi.geometry.iloc[0].exterior.coords)
        assert 7 <= n_coords <= 9
    
    def test_multipolygon_aoi(self):
        """Test generation of multi-polygon AOI."""
        aoi = generate_synthetic_aoi(shape='multipolygon', seed=42)
        
        assert isinstance(aoi.geometry.iloc[0], MultiPolygon)
        assert len(aoi.geometry.iloc[0].geoms) == 2
    
    def test_aoi_deterministic(self):
        """Test that AOI generation is deterministic with same seed."""
        aoi1 = generate_synthetic_aoi(shape='square', seed=42)
        aoi2 = generate_synthetic_aoi(shape='square', seed=42)
        
        assert aoi1.geometry.iloc[0].equals(aoi2.geometry.iloc[0])
    
    def test_aoi_different_seeds(self):
        """Test that different seeds produce different results."""
        aoi1 = generate_synthetic_aoi(shape='polygon', seed=42)
        aoi2 = generate_synthetic_aoi(shape='polygon', seed=99)
        
        assert not aoi1.geometry.iloc[0].equals(aoi2.geometry.iloc[0])
    
    def test_aoi_custom_size(self):
        """Test AOI generation with custom size."""
        size = 10000.0  # 10km
        aoi = generate_synthetic_aoi(shape='square', size=size, seed=42)
        
        # For a square, area should be approximately size^2
        area = aoi.geometry.iloc[0].area
        expected_area = size * size
        assert 0.8 * expected_area <= area <= 1.2 * expected_area
    
    def test_aoi_custom_crs(self):
        """Test AOI generation with different CRS."""
        aoi = generate_synthetic_aoi(shape='square', crs='EPSG:4326', seed=42)
        assert aoi.crs.to_string() == 'EPSG:4326'
    
    def test_aoi_invalid_shape(self):
        """Test that invalid shape raises error."""
        with pytest.raises(ValueError, match="Unknown shape"):
            generate_synthetic_aoi(shape='invalid_shape')


class TestSyntheticRaster:
    """Tests for raster generation."""
    
    def test_basic_raster(self):
        """Test basic raster generation."""
        ds = generate_synthetic_raster(n_x=10, n_y=10, seed=42)
        
        assert isinstance(ds, xr.Dataset)
        assert ds.sizes['x'] == 10
        assert ds.sizes['y'] == 10
    
    def test_raster_coordinates(self):
        """Test that raster has required coordinates."""
        ds = generate_synthetic_raster(n_x=5, n_y=5, seed=42)
        
        # Should have x, y, X, Y coordinates
        assert 'x' in ds.coords
        assert 'y' in ds.coords
        assert 'X' in ds.coords
        assert 'Y' in ds.coords
        
        # Should have 2D lat/lon as data variables
        assert 'lat' in ds.data_vars
        assert 'lon' in ds.data_vars
        assert ds['lat'].ndim == 2
        assert ds['lon'].ndim == 2
    
    def test_raster_default_variables(self):
        """Test default variable generation."""
        ds = generate_synthetic_raster(n_x=5, n_y=5, seed=42)
        
        # Default variables
        assert 'tair_avg' in ds.data_vars
        assert 'prec' in ds.data_vars
        assert 'nirr' in ds.data_vars
    
    def test_raster_custom_variables(self):
        """Test custom variable generation."""
        vars = ['tair_avg', 'wind', 'vapo']
        ds = generate_synthetic_raster(n_x=5, n_y=5, variables=vars, seed=42)
        
        for var in vars:
            assert var in ds.data_vars
            assert ds[var].shape == (5, 5)
    
    def test_raster_spatial_ref(self):
        """Test spatial reference metadata."""
        ds = generate_synthetic_raster(n_x=5, n_y=5, seed=42, add_spatial_ref=True)
        
        assert 'spatial_ref' in ds.coords
        assert 'GeoTransform' in ds.spatial_ref.attrs
        assert 'proj4text' in ds.spatial_ref.attrs
    
    def test_raster_no_spatial_ref(self):
        """Test raster without spatial reference."""
        ds = generate_synthetic_raster(n_x=5, n_y=5, seed=42, add_spatial_ref=False)
        
        assert 'spatial_ref' not in ds.coords
    
    def test_raster_deterministic(self):
        """Test that raster generation is deterministic."""
        ds1 = generate_synthetic_raster(n_x=5, n_y=5, variables=['tair_avg'], seed=42)
        ds2 = generate_synthetic_raster(n_x=5, n_y=5, variables=['tair_avg'], seed=42)
        
        np.testing.assert_array_equal(ds1['tair_avg'].values, ds2['tair_avg'].values)
    
    def test_raster_different_seeds(self):
        """Test that different seeds produce different results."""
        ds1 = generate_synthetic_raster(n_x=5, n_y=5, variables=['tair_avg'], seed=42)
        ds2 = generate_synthetic_raster(n_x=5, n_y=5, variables=['tair_avg'], seed=99)
        
        assert not np.array_equal(ds1['tair_avg'].values, ds2['tair_avg'].values)
    
    def test_raster_realistic_values(self):
        """Test that generated values are in realistic ranges."""
        ds = generate_synthetic_raster(n_x=10, n_y=10, seed=42)
        
        # Temperature should be reasonable for Arctic
        tair = ds['tair_avg'].values
        assert tair.min() > -50
        assert tair.max() < 30
        
        # Precipitation should be positive
        prec = ds['prec'].values
        assert (prec >= 0).all()
        
        # Solar radiation should be positive
        nirr = ds['nirr'].values
        assert (nirr >= 0).all()
    
    def test_raster_custom_resolution(self):
        """Test raster with custom resolution."""
        resolution = 8000.0
        ds = generate_synthetic_raster(n_x=5, n_y=5, resolution=resolution, seed=42)
        
        # Check that coordinate spacing matches resolution
        x_spacing = ds.x.values[1] - ds.x.values[0]
        assert abs(x_spacing - resolution) < 0.01
        
        y_spacing = abs(ds.y.values[1] - ds.y.values[0])
        assert abs(y_spacing - resolution) < 0.01


class TestSyntheticTimeseries:
    """Tests for time series generation."""
    
    def test_basic_timeseries(self):
        """Test basic time series generation."""
        datasets = generate_synthetic_timeseries(start_year=1901, n_years=3, n_x=5, n_y=5, seed=42)
        
        assert isinstance(datasets, list)
        assert len(datasets) == 3
        
        for ds in datasets:
            assert isinstance(ds, xr.Dataset)
    
    def test_timeseries_years(self):
        """Test that time series has correct years."""
        start_year = 1905
        n_years = 5
        datasets = generate_synthetic_timeseries(start_year=start_year, n_years=n_years, n_x=5, n_y=5, seed=42)
        
        for i, ds in enumerate(datasets):
            expected_year = start_year + i
            assert ds.attrs['year'] == expected_year
    
    def test_timeseries_has_time_dimension(self):
        """Test that each dataset has time dimension."""
        datasets = generate_synthetic_timeseries(start_year=1901, n_years=2, n_x=5, n_y=5, seed=42)
        
        for ds in datasets:
            assert 'time' in ds.dims
            # Should have 365 or 366 days
            assert ds.sizes['time'] >= 365
            assert ds.sizes['time'] <= 366
    
    def test_timeseries_spatial_dimensions(self):
        """Test spatial dimensions match."""
        datasets = generate_synthetic_timeseries(start_year=1901, n_years=2, n_x=7, n_y=8, seed=42)
        
        for ds in datasets:
            assert ds.sizes['x'] == 7
            assert ds.sizes['y'] == 8
    
    def test_timeseries_default_variables(self):
        """Test default climate variables."""
        datasets = generate_synthetic_timeseries(start_year=1901, n_years=1, n_x=5, n_y=5, seed=42)
        
        ds = datasets[0]
        expected_vars = ['tair_avg', 'tair_max', 'tair_min', 'prec', 'nirr', 'wind', 'vapo', 'winddir']
        
        for var in expected_vars:
            assert var in ds.data_vars
            # Should be 3D: (time, y, x)
            assert ds[var].ndim == 3
    
    def test_timeseries_deterministic(self):
        """Test that time series generation is deterministic."""
        ds1 = generate_synthetic_timeseries(start_year=1901, n_years=2, n_x=5, n_y=5, seed=42)
        ds2 = generate_synthetic_timeseries(start_year=1901, n_years=2, n_x=5, n_y=5, seed=42)
        
        # First year should match
        np.testing.assert_array_equal(
            ds1[0]['tair_avg'].values,
            ds2[0]['tair_avg'].values
        )


class TestSyntheticVegetation:
    """Tests for vegetation data generation."""
    
    def test_basic_vegetation(self):
        """Test basic vegetation generation."""
        ds = generate_synthetic_vegetation(n_x=10, n_y=10, seed=42)
        
        assert isinstance(ds, xr.Dataset)
        assert 'veg_class' in ds.data_vars
    
    def test_vegetation_data_type(self):
        """Test that vegetation classes are integers."""
        ds = generate_synthetic_vegetation(n_x=10, n_y=10, seed=42)
        
        assert ds['veg_class'].dtype == np.int32
    
    def test_vegetation_value_range(self):
        """Test that vegetation classes are in expected range."""
        n_classes = 7
        ds = generate_synthetic_vegetation(n_x=10, n_y=10, n_classes=n_classes, seed=42)
        
        veg_values = ds['veg_class'].values
        assert veg_values.min() >= 0
        assert veg_values.max() < n_classes
    
    def test_vegetation_has_spatial_ref(self):
        """Test that vegetation has spatial reference."""
        ds = generate_synthetic_vegetation(n_x=10, n_y=10, seed=42)
        
        assert 'spatial_ref' in ds.coords


class TestSyntheticTopo:
    """Tests for topography data generation."""
    
    def test_basic_topo(self):
        """Test basic topography generation."""
        ds = generate_synthetic_topo(n_x=10, n_y=10, seed=42)
        
        assert isinstance(ds, xr.Dataset)
        assert 'elevation' in ds.data_vars
        assert 'slope' in ds.data_vars
        assert 'aspect' in ds.data_vars
    
    def test_topo_elevation_positive(self):
        """Test that elevation values are positive."""
        ds = generate_synthetic_topo(n_x=10, n_y=10, seed=42)
        
        # Elevation should generally be positive (we don't go below sea level much)
        assert ds['elevation'].min() > 0
    
    def test_topo_slope_range(self):
        """Test that slope is in valid range."""
        ds = generate_synthetic_topo(n_x=10, n_y=10, seed=42)
        
        slope = ds['slope'].values
        assert (slope >= 0).all()
        assert (slope <= 90).all()  # Slope in degrees
    
    def test_topo_aspect_range(self):
        """Test that aspect is in valid range."""
        ds = generate_synthetic_topo(n_x=10, n_y=10, seed=42)
        
        aspect = ds['aspect'].values
        assert (aspect >= 0).all()
        assert (aspect <= 360).all()
    
    def test_topo_has_spatial_ref(self):
        """Test that topo has spatial reference."""
        ds = generate_synthetic_topo(n_x=10, n_y=10, seed=42)
        
        assert 'spatial_ref' in ds.coords


class TestGeneratorIntegration:
    """Integration tests across multiple generators."""
    
    def test_consistent_spatial_parameters(self):
        """Test that same spatial parameters produce consistent grids."""
        n_x, n_y = 10, 10
        center_x, center_y = -1500000.0, 2700000.0
        resolution = 4000.0
        seed = 42
        
        ds_raster = generate_synthetic_raster(
            n_x=n_x, n_y=n_y,
            center_x=center_x, center_y=center_y,
            resolution=resolution, seed=seed
        )
        
        ds_veg = generate_synthetic_vegetation(
            n_x=n_x, n_y=n_y,
            center_x=center_x, center_y=center_y,
            resolution=resolution, seed=seed
        )
        
        # Coordinates should match
        np.testing.assert_array_equal(ds_raster.x.values, ds_veg.x.values)
        np.testing.assert_array_equal(ds_raster.y.values, ds_veg.y.values)
    
    def test_aoi_and_raster_compatibility(self):
        """Test that AOI and raster have compatible CRS and extent."""
        # Generate AOI
        aoi = generate_synthetic_aoi(
            shape='square',
            center_x=-1500000.0,
            center_y=2700000.0,
            size=40000.0,  # 40km square
            seed=42
        )
        
        # Generate raster covering same area
        ds = generate_synthetic_raster(
            n_x=10, n_y=10,
            center_x=-1500000.0,
            center_y=2700000.0,
            resolution=4000.0,  # 10 pixels * 4km = 40km
            seed=42
        )
        
        # CRS should match
        assert aoi.crs.to_string() == ds.attrs['crs']
        
        # Raster extent should overlap with AOI
        aoi_bounds = aoi.total_bounds
        raster_extent = (
            ds.x.values.min() - ds.attrs['resolution']/2,
            ds.x.values.max() + ds.attrs['resolution']/2,
            ds.y.values.min() - ds.attrs['resolution']/2,
            ds.y.values.max() + ds.attrs['resolution']/2
        )
        
        # Check for overlap (not exact match due to different geometries)
        assert raster_extent[0] < aoi_bounds[2]  # raster left < aoi right
        assert raster_extent[1] > aoi_bounds[0]  # raster right > aoi left
