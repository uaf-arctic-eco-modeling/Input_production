"""
Synthetic test data generators for temds package.

These generators create small, deterministic datasets for unit testing without
requiring external data downloads or large file I/O.
"""

import numpy as np
import xarray as xr
import geopandas as gpd
from shapely.geometry import Polygon, MultiPolygon, box
import pyproj
from datetime import datetime, timedelta
from typing import Literal, Optional
import pandas as pd


def generate_synthetic_aoi(
    shape: Literal['square', 'triangle', 'polygon', 'multipolygon'] = 'square',
    crs: str = 'EPSG:6931',
    center_x: float = -1500000.0,
    center_y: float = 2700000.0,
    size: float = 20000.0,
    seed: int = 42
) -> gpd.GeoDataFrame:
    """
    Generate a synthetic Area of Interest (AOI) as a GeoDataFrame.
    
    Parameters
    ----------
    shape : str
        Type of geometry: 'square', 'triangle', 'polygon', or 'multipolygon'
    crs : str
        Coordinate reference system (default: EPSG:6931 - Arctic)
    center_x, center_y : float
        Center coordinates in the specified CRS
    size : float
        Approximate size in CRS units (20km default)
    seed : int
        Random seed for reproducible 'polygon' shapes
        
    Returns
    -------
    gpd.GeoDataFrame
        GeoDataFrame with single feature containing the AOI geometry
    """
    np.random.seed(seed)
    
    half = size / 2
    
    if shape == 'square':
        geom = box(center_x - half, center_y - half, 
                   center_x + half, center_y + half)
    
    elif shape == 'triangle':
        coords = [
            (center_x, center_y + half),
            (center_x - half, center_y - half),
            (center_x + half, center_y - half),
            (center_x, center_y + half)  # close the ring
        ]
        geom = Polygon(coords)
    
    elif shape == 'polygon':
        # Irregular polygon with 6-8 vertices
        n_vertices = np.random.randint(6, 9)
        angles = np.sort(np.random.uniform(0, 2*np.pi, n_vertices))
        radii = np.random.uniform(half * 0.7, half * 1.0, n_vertices)
        
        coords = [
            (center_x + r * np.cos(a), center_y + r * np.sin(a))
            for a, r in zip(angles, radii)
        ]
        coords.append(coords[0])  # close the ring
        geom = Polygon(coords)
    
    elif shape == 'multipolygon':
        # Two separate square polygons
        offset = half * 0.6
        poly1 = box(center_x - half - offset, center_y - half,
                    center_x - offset, center_y + half)
        poly2 = box(center_x + offset, center_y - half,
                    center_x + half + offset, center_y + half)
        geom = MultiPolygon([poly1, poly2])
    
    else:
        raise ValueError(f"Unknown shape: {shape}")
    
    gdf = gpd.GeoDataFrame(
        {'name': ['test_aoi'], 'geometry': [geom]},
        crs=crs
    )
    
    return gdf


def generate_synthetic_raster(
    n_x: int = 10,
    n_y: int = 10,
    variables: Optional[list[str]] = None,
    crs: str = 'EPSG:6931',
    center_x: float = -1500000.0,
    center_y: float = 2700000.0,
    resolution: float = 4000.0,
    seed: int = 42,
    add_spatial_ref: bool = True
) -> xr.Dataset:
    """
    Generate a synthetic raster dataset with realistic climate variables.
    
    Parameters
    ----------
    n_x, n_y : int
        Number of pixels in x and y dimensions
    variables : list of str, optional
        Variables to include. Default: ['tair_avg', 'prec', 'nirr']
    crs : str
        Coordinate reference system
    center_x, center_y : float
        Center coordinates in the specified CRS
    resolution : float
        Pixel size in CRS units
    seed : int
        Random seed for reproducible data
    add_spatial_ref : bool
        Whether to add spatial_ref coordinate with GeoTransform
        
    Returns
    -------
    xr.Dataset
        Dataset with synthetic climate data
    """
    np.random.seed(seed)
    
    if variables is None:
        variables = ['tair_avg', 'prec', 'nirr']
    
    # Calculate extents
    half_width = (n_x * resolution) / 2
    half_height = (n_y * resolution) / 2
    
    x_min = center_x - half_width
    y_max = center_y + half_height
    
    # Create coordinate arrays
    x_coords = np.arange(x_min + resolution/2, x_min + n_x * resolution, resolution)
    y_coords = np.arange(y_max - resolution/2, y_max - n_y * resolution, -resolution)
    
    # Create X and Y coordinate arrays (projected coordinates)
    X = x_coords
    Y = y_coords
    
    # Create lat/lon coordinates (approximate for Arctic region)
    crs_obj = pyproj.CRS(crs)
    transformer = pyproj.Transformer.from_crs(crs_obj, "EPSG:4326", always_xy=True)
    
    # Create 2D grids
    x_grid, y_grid = np.meshgrid(x_coords, y_coords)
    lon_grid, lat_grid = transformer.transform(x_grid, y_grid)
    
    # Build dataset
    ds = xr.Dataset(
        coords={
            'x': (['x'], x_coords),
            'y': (['y'], y_coords),
            'X': (['x'], X),
            'Y': (['y'], Y),
        }
    )
    
    # Add 2D lat/lon coordinates
    ds['lat'] = xr.DataArray(lat_grid, dims=['y', 'x'])
    ds['lon'] = xr.DataArray(lon_grid, dims=['y', 'x'])
    
    # Generate synthetic data with realistic patterns
    for var in variables:
        if 'tair' in var or 'temp' in var:
            # Temperature: gradient from south to north + noise
            base = -5.0 + np.arange(n_y)[:, np.newaxis] * 0.5
            noise = np.random.normal(0, 2.0, (n_y, n_x))
            data = base + noise
            units = 'celsius'
            
        elif 'prec' in var:
            # Precipitation: positive values with spatial pattern
            base = 50.0 + np.random.uniform(0, 30, (n_y, n_x))
            data = np.maximum(0, base)
            units = 'mm'
            
        elif 'nirr' in var or 'rsds' in var:
            # Solar radiation: positive with seasonal-like variation
            data = 150.0 + np.random.uniform(-50, 50, (n_y, n_x))
            data = np.maximum(0, data)
            units = 'W/m2'
            
        elif 'vapo' in var or 'vapor' in var:
            # Vapor pressure: small positive values
            data = 5.0 + np.random.uniform(-1, 3, (n_y, n_x))
            data = np.maximum(0.1, data)
            units = 'hPa'
            
        elif 'wind' in var:
            # Wind speed: positive values
            data = 3.0 + np.random.uniform(0, 5, (n_y, n_x))
            units = 'm/s'
            
        else:
            # Generic variable
            data = np.random.normal(100, 20, (n_y, n_x))
            units = 'unknown'
        
        ds[var] = xr.DataArray(
            data,
            dims=['y', 'x'],
            attrs={'units': units, 'long_name': var}
        )
    
    # Add spatial reference metadata
    if add_spatial_ref:
        ds = ds.assign_coords({
            'spatial_ref': xr.DataArray(
                0,
                attrs={
                    'spatial_ref': crs,
                    'GeoTransform': f"{x_min} {resolution} 0 {y_max} 0 -{resolution}",
                    'proj4text': crs_obj.to_proj4()
                }
            )
        })
    
    # Global attributes
    ds.attrs.update({
        'crs': crs,
        'resolution': resolution,
        'source': 'synthetic_test_data',
        'created': datetime.now().isoformat()
    })
    
    return ds


def generate_synthetic_timeseries(
    start_year: int = 1901,
    n_years: int = 3,
    n_x: int = 10,
    n_y: int = 10,
    variables: Optional[list[str]] = None,
    crs: str = 'EPSG:6931',
    center_x: float = -1500000.0,
    center_y: float = 2700000.0,
    resolution: float = 4000.0,
    seed: int = 42
) -> list[xr.Dataset]:
    """
    Generate a synthetic time series of yearly datasets.
    
    Parameters
    ----------
    start_year : int
        First year in the series
    n_years : int
        Number of years to generate
    n_x, n_y : int
        Spatial dimensions
    variables : list of str, optional
        Climate variables to include
    Other parameters : same as generate_synthetic_raster
        
    Returns
    -------
    list of xr.Dataset
        List of datasets, one per year, suitable for YearlyTimeSeries
    """
    if variables is None:
        variables = ['tair_avg', 'tair_max', 'tair_min', 'prec', 'nirr', 
                     'wind', 'vapo', 'winddir']
    
    datasets = []
    
    for year_offset in range(n_years):
        year = start_year + year_offset
        
        # Use different seed per year for variation
        year_seed = seed + year_offset
        
        # Generate base raster
        ds = generate_synthetic_raster(
            n_x=n_x, n_y=n_y, variables=variables,
            crs=crs, center_x=center_x, center_y=center_y,
            resolution=resolution, seed=year_seed
        )
        
        # Add time dimension with daily timesteps for the year
        n_days = 366 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 365
        
        times = pd.date_range(
            start=f'{year}-01-01',
            periods=n_days,
            freq='D'
        )
        
        # Expand each variable to have time dimension
        data_vars = {}
        for var in variables:
            # Create seasonal variation in the data
            seasonal = np.sin(np.arange(n_days) / n_days * 2 * np.pi)
            
            # Broadcast spatial pattern across time with seasonal variation
            spatial_data = ds[var].values  # (y, x)
            time_data = spatial_data[np.newaxis, :, :] + seasonal[:, np.newaxis, np.newaxis] * 2
            
            data_vars[var] = xr.DataArray(
                time_data,
                dims=['time', 'y', 'x'],
                attrs=ds[var].attrs
            )
        
        # Create yearly dataset
        yearly_ds = xr.Dataset(
            data_vars,
            coords={
                'time': times,
                'x': ds.x,
                'y': ds.y,
                'X': ds.X,
                'Y': ds.Y,
                'lat': ds.lat,
                'lon': ds.lon
            }
        )
        
        if 'spatial_ref' in ds.coords:
            yearly_ds = yearly_ds.assign_coords({'spatial_ref': ds.spatial_ref})
        
        yearly_ds.attrs.update(ds.attrs)
        yearly_ds.attrs['year'] = year
        
        datasets.append(yearly_ds)
    
    return datasets


def generate_synthetic_vegetation(
    n_x: int = 10,
    n_y: int = 10,
    n_classes: int = 5,
    crs: str = 'EPSG:6931',
    center_x: float = -1500000.0,
    center_y: float = 2700000.0,
    resolution: float = 4000.0,
    seed: int = 42
) -> xr.Dataset:
    """
    Generate synthetic vegetation classification raster.
    
    Returns dataset with 'veg_class' variable containing integer codes.
    """
    np.random.seed(seed)
    
    ds = generate_synthetic_raster(
        n_x=n_x, n_y=n_y, variables=[],
        crs=crs, center_x=center_x, center_y=center_y,
        resolution=resolution, seed=seed, add_spatial_ref=True
    )
    
    # Create patchy vegetation pattern
    veg_data = np.random.randint(0, n_classes, (n_y, n_x), dtype=np.int32)
    
    ds['veg_class'] = xr.DataArray(
        veg_data,
        dims=['y', 'x'],
        attrs={
            'long_name': 'vegetation class',
            'units': 'class',
            '_FillValue': -9999
        }
    )
    
    return ds


def generate_synthetic_topo(
    n_x: int = 10,
    n_y: int = 10,
    crs: str = 'EPSG:6931',
    center_x: float = -1500000.0,
    center_y: float = 2700000.0,
    resolution: float = 4000.0,
    seed: int = 42
) -> xr.Dataset:
    """
    Generate synthetic topography data (elevation, slope, aspect).
    """
    np.random.seed(seed)
    
    ds = generate_synthetic_raster(
        n_x=n_x, n_y=n_y, variables=[],
        crs=crs, center_x=center_x, center_y=center_y,
        resolution=resolution, seed=seed, add_spatial_ref=True
    )
    
    # Elevation: gradient from low to high
    elev_base = 200 + np.arange(n_y)[:, np.newaxis] * 50
    elev_noise = np.random.normal(0, 20, (n_y, n_x))
    elevation = elev_base + elev_noise
    
    ds['elevation'] = xr.DataArray(
        elevation,
        dims=['y', 'x'],
        attrs={'long_name': 'elevation', 'units': 'm'}
    )
    
    # Slope: derived from elevation
    slope = np.random.uniform(0, 15, (n_y, n_x))
    ds['slope'] = xr.DataArray(
        slope,
        dims=['y', 'x'],
        attrs={'long_name': 'slope', 'units': 'degrees'}
    )
    
    # Aspect: circular
    aspect = np.random.uniform(0, 360, (n_y, n_x))
    ds['aspect'] = xr.DataArray(
        aspect,
        dims=['y', 'x'],
        attrs={'long_name': 'aspect', 'units': 'degrees'}
    )
    
    return ds
