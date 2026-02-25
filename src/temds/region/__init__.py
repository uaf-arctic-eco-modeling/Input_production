"""
Spatial region abstractions for temds.

This module provides protocols and base classes for working with spatial
regions (AOI, Tiles, etc.) in a consistent way.
"""

from .base import (
    SpatialRegion,
    SpatialRegionWithData,
    validate_spatial_region,
    validate_spatial_region_with_data,
    check_regions_compatible,
    get_region_info,
    RegionCompatibilityError,
)
from .region import RegionOfInterest
from .mask import Mask

__all__ = [
    'SpatialRegion',
    'SpatialRegionWithData',
    'validate_spatial_region',
    'validate_spatial_region_with_data',
    'check_regions_compatible',
    'get_region_info',
    'RegionCompatibilityError',
    'RegionOfInterest',
    'Mask',
]
