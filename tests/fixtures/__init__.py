"""Test fixtures for temds package."""

from .generators import (
    generate_synthetic_aoi,
    generate_synthetic_raster,
    generate_synthetic_timeseries,
    generate_synthetic_vegetation,
    generate_synthetic_topo,
)

__all__ = [
    'generate_synthetic_aoi',
    'generate_synthetic_raster',
    'generate_synthetic_timeseries',
    'generate_synthetic_vegetation',
    'generate_synthetic_topo',
]
