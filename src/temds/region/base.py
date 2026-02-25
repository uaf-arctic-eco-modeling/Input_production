"""
Base abstractions for spatial regions in temds.

This module defines the common interface (Protocol) that all spatial region
types should implement: AOI, Tile, RegionOfInterest, etc.

Using Protocols (PEP 544) allows for structural subtyping - classes don't need
to explicitly inherit from the protocol, they just need to implement the
required methods and properties.
"""

from typing import Protocol, Tuple, Optional, runtime_checkable
import pyproj
import xarray as xr
import geopandas as gpd
from pathlib import Path


@runtime_checkable
class SpatialRegion(Protocol):
    """
    Protocol defining the common interface for spatial regions.
    
    This protocol establishes a contract that all spatial region types 
    (AOI, Tile, etc.) should follow. It enables polymorphic behavior without
    requiring inheritance.
    
    Classes implementing this protocol should provide:
    - Spatial extent information (bounds and CRS)
    - Raster mask representation
    - File I/O capabilities
    
    Example
    -------
    >>> def process_region(region: SpatialRegion):
    ...     extent = region.extent
    ...     mask = region.mask
    ...     # Process the region...
    
    This function can accept any object that implements the SpatialRegion
    protocol (AOI, Tile, etc.) without knowing its concrete type.
    """
    
    @property
    def extent(self) -> Tuple[float, float, float, float]:
        """
        Spatial extent of the region as (minx, maxx, miny, maxy).
        
        Returns
        -------
        tuple of float
            (minx, maxx, miny, maxy) in the region's CRS
        """
        ...
    
    @property
    def crs(self) -> pyproj.CRS:
        """
        Coordinate Reference System of the region.
        
        Returns
        -------
        pyproj.CRS
            The CRS object
        """
        ...
    
    @property
    def mask(self) -> xr.DataArray:
        """
        Raster mask indicating which pixels are part of the region.
        
        Returns
        -------
        xr.DataArray
            Boolean or integer mask array with spatial coordinates
            True/1 = inside region, False/0 = outside region
        """
        ...
    
    def to_rasterfile(self, path: Path, **kwargs) -> Path:
        """
        Save the region mask as a raster file.
        
        Parameters
        ----------
        path : Path
            Output directory or file path
        **kwargs
            Additional arguments for the specific implementation
            
        Returns
        -------
        Path
            Path to the saved raster file
        """
        ...


@runtime_checkable
class SpatialRegionWithData(SpatialRegion, Protocol):
    """
    Extended protocol for spatial regions that contain datasets.
    
    This extends SpatialRegion to include data management capabilities,
    as used by Tile and RegionOfInterest classes.
    """
    
    @property
    def data(self) -> dict:
        """
        Dictionary of datasets associated with this region.
        
        Keys are dataset names (e.g., 'worldclim', 'cru', 'vegetation'),
        values are TEMDataset or YearlyTimeSeries objects.
        
        Returns
        -------
        dict
            Mapping of dataset names to data objects
        """
        ...
    
    def import_and_normalize(self, name: str, dataset, **kwargs):
        """
        Import a dataset and normalize it to the region's spatial grid.
        
        Parameters
        ----------
        name : str
            Name to assign to the dataset in self.data
        dataset
            Dataset to import (TEMDataset or YearlyTimeSeries)
        **kwargs
            Additional normalization parameters
        """
        ...
    
    def export(self, format: str, output_path: Path, **kwargs) -> Path:
        """
        Export the region's data in a specified format.
        
        Parameters
        ----------
        format : str
            Export format (e.g., 'TEM', 'raw', 'netcdf')
        output_path : Path
            Where to save exported data
        **kwargs
            Format-specific export options
            
        Returns
        -------
        Path
            Path to exported data
        """
        ...


def validate_spatial_region(obj) -> bool:
    """
    Check if an object implements the SpatialRegion protocol.
    
    Parameters
    ----------
    obj
        Object to check
        
    Returns
    -------
    bool
        True if obj implements SpatialRegion protocol
        
    Example
    -------
    >>> aoi = AOIMask.load_vector('path/to/aoi.shp')
    >>> validate_spatial_region(aoi)
    True
    """
    return isinstance(obj, SpatialRegion)


def validate_spatial_region_with_data(obj) -> bool:
    """
    Check if an object implements the SpatialRegionWithData protocol.
    
    Parameters
    ----------
    obj
        Object to check
        
    Returns
    -------
    bool
        True if obj implements SpatialRegionWithData protocol
    """
    return isinstance(obj, SpatialRegionWithData)


class RegionCompatibilityError(Exception):
    """Raised when spatial regions are incompatible (different CRS, resolution, etc.)."""
    pass


def check_regions_compatible(
    region1: SpatialRegion,
    region2: SpatialRegion,
    check_extent: bool = False
) -> bool:
    """
    Check if two spatial regions are compatible (same CRS).
    
    Parameters
    ----------
    region1, region2 : SpatialRegion
        Regions to compare
    check_extent : bool
        If True, also check that extents overlap
        
    Returns
    -------
    bool
        True if regions are compatible
        
    Raises
    ------
    RegionCompatibilityError
        If regions are incompatible
    """
    # Check CRS
    if region1.crs != region2.crs:
        raise RegionCompatibilityError(
            f"Regions have different CRS: {region1.crs} vs {region2.crs}"
        )
    
    # Check extent overlap if requested
    if check_extent:
        ext1 = region1.extent
        ext2 = region2.extent
        
        # Check if extents overlap
        overlap_x = not (ext1[1] < ext2[0] or ext2[1] < ext1[0])
        overlap_y = not (ext1[3] < ext2[2] or ext2[3] < ext1[2])
        
        if not (overlap_x and overlap_y):
            raise RegionCompatibilityError(
                f"Regions do not overlap in space"
            )
    
    return True


def get_region_info(region: SpatialRegion) -> dict:
    """
    Extract summary information from a spatial region.
    
    Parameters
    ----------
    region : SpatialRegion
        Region to summarize
        
    Returns
    -------
    dict
        Dictionary with region properties: extent, crs, has_data, etc.
    """
    info = {
        'extent': region.extent,
        'crs': region.crs.to_string(),
        'has_mask': hasattr(region, 'mask'),
    }
    
    # Check for data capabilities
    if isinstance(region, SpatialRegionWithData):
        info['has_data'] = True
        info['datasets'] = list(region.data.keys() if hasattr(region, 'data') else [])
    else:
        info['has_data'] = False
    
    return info
