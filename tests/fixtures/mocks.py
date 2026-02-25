"""
Mock utilities for patching external data sources and file I/O in tests.

These mocks replace expensive operations (downloads, large file reads) with
synthetic test data, allowing fast unit tests without external dependencies.
"""

from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
from typing import Optional, Callable
import xarray as xr
import rasterio
from rasterio.io import MemoryFile
import numpy as np

from .generators import (
    generate_synthetic_raster,
    generate_synthetic_timeseries,
    generate_synthetic_vegetation,
    generate_synthetic_topo,
)


class MockRasterioDataset:
    """Mock rasterio dataset that behaves like a real raster file."""
    
    def __init__(self, data: np.ndarray, crs: str, transform, nodata=-9999):
        self.data = data
        self.crs = rasterio.crs.CRS.from_string(crs)
        self.transform = transform
        self.nodata = nodata
        self.shape = data.shape if len(data.shape) == 2 else data.shape[1:]
        self.count = 1 if len(data.shape) == 2 else data.shape[0]
        self.width = self.shape[1]
        self.height = self.shape[0]
        self.bounds = rasterio.transform.array_bounds(self.height, self.width, transform)
        
    def read(self, indexes=None, masked=False):
        """Mock read method."""
        if indexes is None:
            return self.data
        if isinstance(indexes, int):
            if len(self.data.shape) == 2:
                return self.data
            return self.data[indexes - 1]
        return self.data
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass


def mock_rasterio_open(synthetic_dataset: xr.Dataset) -> Callable:
    """
    Create a mock function for rasterio.open that returns synthetic data.
    
    Parameters
    ----------
    synthetic_dataset : xr.Dataset
        Dataset from generate_synthetic_raster or similar
        
    Returns
    -------
    Callable
        Function that can replace rasterio.open
        
    Example
    -------
    >>> ds = generate_synthetic_raster(n_x=10, n_y=10)
    >>> with patch('rasterio.open', mock_rasterio_open(ds)):
    ...     # Code that calls rasterio.open will get synthetic data
    ...     result = some_function_that_uses_rasterio()
    """
    
    def _mock_open(filepath, *args, **kwargs):
        # Extract first variable as raster data
        var_name = list(synthetic_dataset.data_vars)[0]
        data = synthetic_dataset[var_name].values
        
        # Get transform from spatial_ref if available
        if 'spatial_ref' in synthetic_dataset.coords:
            geotrans_str = synthetic_dataset.spatial_ref.attrs.get('GeoTransform', '')
            parts = [float(x) for x in geotrans_str.split()]
            transform = rasterio.transform.Affine(
                parts[1], parts[2], parts[0],
                parts[4], parts[5], parts[3]
            )
            crs = synthetic_dataset.spatial_ref.attrs.get('spatial_ref', 'EPSG:6931')
        else:
            # Default transform
            resolution = synthetic_dataset.attrs.get('resolution', 4000.0)
            x_min = float(synthetic_dataset.x.values[0]) - resolution / 2
            y_max = float(synthetic_dataset.y.values[0]) + resolution / 2
            transform = rasterio.transform.from_origin(x_min, y_max, resolution, resolution)
            crs = synthetic_dataset.attrs.get('crs', 'EPSG:6931')
        
        return MockRasterioDataset(data, crs, transform)
    
    return _mock_open


def mock_xarray_open_dataset(synthetic_dataset: xr.Dataset) -> Callable:
    """
    Create a mock function for xr.open_dataset that returns synthetic data.
    
    Parameters
    ----------
    synthetic_dataset : xr.Dataset
        Dataset to return when xr.open_dataset is called
        
    Returns
    -------
    Callable
        Function that can replace xr.open_dataset
        
    Example
    -------
    >>> ds = generate_synthetic_raster(n_x=10, n_y=10)
    >>> with patch('xarray.open_dataset', mock_xarray_open_dataset(ds)):
    ...     result = some_function_that_uses_xarray()
    """
    
    def _mock_open(filepath, *args, **kwargs):
        # Return a copy so each call gets independent data
        return synthetic_dataset.copy(deep=True)
    
    return _mock_open


def mock_worldclim_download(n_x: int = 10, n_y: int = 10, seed: int = 42):
    """
    Mock WorldClim download functionality.
    
    Returns a context manager that patches the download and file reading
    to return synthetic data instead.
    
    Example
    -------
    >>> with mock_worldclim_download(n_x=10, n_y=10):
    ...     # This will use synthetic data instead of downloading
    ...     ds = TEMDataset.from_worldclim(...)
    """
    # Generate synthetic worldclim data
    variables = ['tair_1', 'tair_2', 'tair_3', 'tair_4', 'tair_5', 'tair_6',
                 'tair_7', 'tair_8', 'tair_9', 'tair_10', 'tair_11', 'tair_12',
                 'prec_1', 'prec_2', 'prec_3', 'prec_4', 'prec_5', 'prec_6',
                 'prec_7', 'prec_8', 'prec_9', 'prec_10', 'prec_11', 'prec_12']
    
    ds = generate_synthetic_raster(n_x=n_x, n_y=n_y, variables=variables, seed=seed)
    
    # Return a context manager that patches both download and file reading
    from unittest.mock import patch
    
    class MockWorldClimContext:
        def __enter__(self):
            self.patches = []
            # Mock file existence checks
            self.patches.append(patch('pathlib.Path.exists', return_value=True))
            self.patches.append(patch('pathlib.Path.is_file', return_value=True))
            # Mock rasterio and xarray opens
            self.patches.append(patch('rasterio.open', mock_rasterio_open(ds)))
            self.patches.append(patch('xarray.open_dataset', mock_xarray_open_dataset(ds)))
            
            for p in self.patches:
                p.__enter__()
            return self
        
        def __exit__(self, *args):
            for p in reversed(self.patches):
                p.__exit__(*args)
    
    return MockWorldClimContext()


def mock_crujra_files(
    start_year: int = 1901,
    n_years: int = 3,
    n_x: int = 10,
    n_y: int = 10,
    seed: int = 42
):
    """
    Mock CRU-JRA file reading for time series data.
    
    Returns a context manager that patches file operations to return
    synthetic yearly datasets.
    
    Example
    -------
    >>> with mock_crujra_files(start_year=1901, n_years=3):
    ...     ts = YearlyTimeSeries(Path('fake/path'), logger=log)
    """
    
    datasets = generate_synthetic_timeseries(
        start_year=start_year,
        n_years=n_years,
        n_x=n_x,
        n_y=n_y,
        seed=seed
    )
    
    # Create a mapping of year to dataset
    year_to_ds = {start_year + i: ds for i, ds in enumerate(datasets)}
    
    def mock_open_for_year(filepath, *args, **kwargs):
        """Extract year from filepath and return corresponding dataset."""
        path_str = str(filepath)
        # Try to extract year from filename (e.g., "something_1901.nc")
        import re
        match = re.search(r'(\d{4})', path_str)
        if match:
            year = int(match.group(1))
            if year in year_to_ds:
                return year_to_ds[year].copy(deep=True)
        # Default to first year
        return datasets[0].copy(deep=True)
    
    class MockCRUJRAContext:
        def __enter__(self):
            self.patches = []
            self.patches.append(patch('pathlib.Path.exists', return_value=True))
            self.patches.append(patch('pathlib.Path.is_file', return_value=True))
            self.patches.append(patch('pathlib.Path.is_dir', return_value=True))
            
            # Mock glob to return fake files for each year
            fake_files = [Path(f'fake_path/data_{year}.nc') for year in year_to_ds.keys()]
            self.patches.append(patch('pathlib.Path.glob', return_value=fake_files))
            
            # Mock xarray open to return appropriate dataset by year
            self.patches.append(patch('xarray.open_dataset', mock_open_for_year))
            
            for p in self.patches:
                p.__enter__()
            return self
        
        def __exit__(self, *args):
            for p in reversed(self.patches):
                p.__exit__(*args)
    
    return MockCRUJRAContext()


def create_tmp_workspace(tmp_path: Path) -> Path:
    """
    Create a temporary workspace directory structure for testing.
    
    Parameters
    ----------
    tmp_path : Path
        pytest tmp_path fixture
        
    Returns
    -------
    Path
        Root of the workspace with standard working/ subdirectories
    """
    workspace = tmp_path / "test_workspace"
    
    # Create standard directory structure
    dirs = [
        "working/00-download/worldclim",
        "working/00-download/vegetation",
        "working/00-download/topo",
        "working/00-download/soiltexture",
        "working/01-aoi",
        "working/02-data",
        "working/03-tiles",
        "working/04-downscaled-tiles-results",
        "working/05-tiles-TEM",
    ]
    
    for dir_path in dirs:
        (workspace / dir_path).mkdir(parents=True, exist_ok=True)
    
    return workspace


def save_synthetic_fixture(
    output_path: Path,
    fixture_type: str = 'raster',
    **kwargs
):
    """
    Save a synthetic dataset to disk as a real file for integration testing.
    
    Parameters
    ----------
    output_path : Path
        Where to save the fixture file
    fixture_type : str
        Type of fixture: 'raster', 'timeseries', 'vegetation', 'topo'
    **kwargs
        Passed to the generator function
        
    Example
    -------
    >>> save_synthetic_fixture(
    ...     Path('tests/fixtures/real_data/small_worldclim.nc'),
    ...     fixture_type='raster',
    ...     n_x=10, n_y=10
    ... )
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if fixture_type == 'raster':
        ds = generate_synthetic_raster(**kwargs)
    elif fixture_type == 'vegetation':
        ds = generate_synthetic_vegetation(**kwargs)
    elif fixture_type == 'topo':
        ds = generate_synthetic_topo(**kwargs)
    elif fixture_type == 'timeseries':
        datasets = generate_synthetic_timeseries(**kwargs)
        # Save each year separately
        start_year = kwargs.get('start_year', 1901)
        for i, ds in enumerate(datasets):
            year_path = output_path.parent / f"{output_path.stem}_{start_year + i}.nc"
            ds.to_netcdf(year_path)
        return
    else:
        raise ValueError(f"Unknown fixture type: {fixture_type}")
    
    ds.to_netcdf(output_path)
