# Synthetic Test Data Generators

## Overview

Fast, deterministic synthetic data generators for testing the `temds` package without requiring external data downloads or large file I/O operations.

## What's Been Implemented

### 1. Generator Functions ([tests/fixtures/generators.py](../tests/fixtures/generators.py))

**AOI Generation:**
- `generate_synthetic_aoi()` - Creates vector polygons (square, triangle, irregular polygon, multipolygon)
- Configurable: shape, size, center coordinates, CRS
- Produces valid GeoDataFrames compatible with `temds.aoitools.AOIMask`

**Raster Generation:**
- `generate_synthetic_raster()` - Creates small xarray Datasets with climate variables
- Default variables: tair_avg, prec, nirr (configurable)
- Includes: spatial coordinates (x, y, X, Y), lat/lon grids, spatial_ref metadata
- Realistic value ranges for Arctic climate data

**Time Series Generation:**
- `generate_synthetic_timeseries()` - Creates multi-year datasets with daily timesteps
- Each year has 365/366 days with seasonal variation
- Compatible with `temds.datasources.timeseries.YearlyTimeSeries`

**Ancillary Data:**
- `generate_synthetic_vegetation()` - Integer classification rasters
- `generate_synthetic_topo()` - Elevation, slope, aspect datasets

### 2. Test Fixtures ([tests/conftest.py](../tests/conftest.py))

**Session-scoped fixtures** (computed once per test session):
- `synthetic_worldclim_data` - 12 months of temperature and precipitation
- `synthetic_cru_timeseries` - 3 years of daily climate data
- `synthetic_vegetation_data`, `synthetic_topo_data`

**Parameterized fixtures** for comprehensive testing:
- `aoi_shape` - Tests with square, triangle, polygon shapes
- `raster_sizes` - Tests with 5x5, 10x10, 20x20 grids

**Utility fixtures:**
- `tmp_workspace` - Creates temp directory with standard `working/` structure
- `logger` - Standard test logger
- `small_test_aoi`, `tiny_raster` - Minimal datasets for fast unit tests

### 3. Mock Utilities ([tests/fixtures/mocks.py](../tests/fixtures/mocks.py))

**For future use:**
- `mock_rasterio_open()` - Replace rasterio file reads with synthetic data
- `mock_xarray_open_dataset()` - Replace xarray file reads
- `mock_worldclim_download()`, `mock_crujra_files()` - Patch download operations
- `create_tmp_workspace()` - Standard directory structure for tests

### 4. Comprehensive Test Suite ([tests/test_generators.py](../tests/test_generators.py))

**36 tests covering:**
- AOI generation (9 tests) - all shapes, determinism, custom parameters
- Raster generation (10 tests) - coordinates, variables, spatial ref, realistic values
- Time series (6 tests) - temporal structure, consistency
- Vegetation (4 tests) - data types, value ranges
- Topography (5 tests) - realistic elevation/slope/aspect
- Integration (2 tests) - cross-generator compatibility

**All tests pass in < 1 second**

## Key Features

✅ **Deterministic**: Same seed produces identical output  
✅ **Fast**: All 36 tests run in ~0.5 seconds  
✅ **No external dependencies**: No downloads, no large files  
✅ **Realistic**: Value ranges match actual Arctic climate data  
✅ **Compatible**: Works with existing temds classes (AOIMask, TEMDataset, Tile)  
✅ **Flexible**: Configurable sizes, resolutions, variables, CRS  

## Usage Examples

### Basic Usage

```python
from tests.fixtures.generators import generate_synthetic_aoi, generate_synthetic_raster

# Create a small test AOI
aoi = generate_synthetic_aoi(shape='square', size=20000.0, seed=42)

# Create a tiny raster for fast tests
ds = generate_synthetic_raster(n_x=5, n_y=5, variables=['tair_avg', 'prec'], seed=42)
```

### Using Fixtures in Tests

```python
def test_my_feature(synthetic_worldclim_data, small_test_aoi):
    """Test using pre-generated fixtures."""
    # synthetic_worldclim_data is already computed once per session
    assert 'tair_1' in synthetic_worldclim_data.data_vars
    
    # small_test_aoi is a simple square AOI
    assert len(small_test_aoi) == 1
```

### Parameterized Testing

```python
def test_all_aoi_shapes(aoi_shape):
    """Automatically tests with square, triangle, and polygon."""
    aoi = generate_synthetic_aoi(shape=aoi_shape, seed=42)
    # This test runs 3 times with different shapes
```

### Creating Temporary Workspaces

```python
def test_workflow(tmp_workspace):
    """Test with standard directory structure."""
    # tmp_workspace has: working/00-download/, working/01-aoi/, etc.
    aoi_path = tmp_workspace / 'working/01-aoi/test.shp'
    # No cleanup needed - pytest handles it
```

## Benefits for Development

1. **Rapid iteration**: Don't wait for downloads or large file I/O during development
2. **CI/CD friendly**: Tests run quickly in continuous integration
3. **Isolated testing**: Each test gets fresh synthetic data, no shared state
4. **Edge case testing**: Easy to create specific corner cases (empty arrays, single pixels, etc.)
5. **Backwards compatible**: Old tests still work, new tests can use synthetic data

## Next Steps

The generators provide a solid foundation for:
- Testing the SpatialRegion protocol implementation
- Validating workflow orchestration logic
- Unit testing individual functions in corrections.py, downscalers.py
- Integration testing full pipelines without multi-GB datasets

## Files Created

```
tests/
├── fixtures/
│   ├── __init__.py           # Exports generators
│   ├── generators.py         # Core generator functions (500+ lines)
│   └── mocks.py              # Mock utilities for patching (300+ lines)
├── conftest.py               # Pytest fixtures (expanded)
└── test_generators.py        # Comprehensive tests (400+ lines)
```

All tests passing: ✅ 36/36
