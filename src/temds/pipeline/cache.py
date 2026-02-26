"""Cache management for pipeline steps."""

import os
from pathlib import Path
from typing import Optional, Dict, Any
import xarray as xr
import yaml


class CacheManager:
    """Manages caching of intermediate pipeline outputs.
    
    Provides standardized paths and validation for cached data files
    on a per-AOI, per-step basis.
    """
    
    def __init__(self, base_dir: str | Path, aoi_name: str, resolution: int = 1000, crs: str = "EPSG:6931"):
        """Initialize cache manager.
        
        Args:
            base_dir: Base directory for caching (e.g., 'working')
            aoi_name: Name of the AOI being processed
            resolution: Spatial resolution in meters
            crs: Coordinate reference system (default Arctic LAEA)
        """
        self.base_dir = Path(base_dir)
        self.aoi_name = aoi_name
        self.resolution = resolution
        self.crs = crs
        
        # AOI-specific directories
        self.aoi_dir = self.base_dir / "01-aoi" / aoi_name
        self.data_dir = self.base_dir / f"02-{aoi_name}"
        self.tile_dir = self.base_dir / f"03-{aoi_name}"
        
    def get_path(self, step_name: str, **kwargs) -> Path:
        """Get standardized cache path for a step.
        
        Args:
            step_name: Name of the pipeline step
            **kwargs: Additional parameters (e.g., tile_index, year)
            
        Returns:
            Path object for the cache file
        """
        if step_name == "aoi_vector":
            return self.aoi_dir / f"{self.aoi_name}.geojson"
            
        elif step_name == "aoi_raster":
            crs_code = self.crs.split(':')[1]
            return self.aoi_dir / f"{self.aoi_name}_{crs_code}_{self.resolution}m.tiff"
            
        elif step_name == "worldclim":
            crs_code = self.crs.split(':')[1]
            return self.data_dir / f"{self.aoi_name}_wc_{crs_code}_{self.resolution}m.nc"
            
        elif step_name == "vegetation":
            return self.data_dir / f"{self.aoi_name}_veg.nc"
            
        elif step_name == "topography":
            return self.data_dir / f"{self.aoi_name}_topo.nc"
            
        elif step_name == "soil_texture":
            return self.data_dir / f"{self.aoi_name}_soiltex.nc"
            
        elif step_name == "fri":
            return self.data_dir / f"{self.aoi_name}_fri-fire.nc"
            
        elif step_name == "cru":
            return self.data_dir / f"{self.aoi_name}_cru"
            
        elif step_name == "tile_index":
            return self.tile_dir / "tiles" / "tile_index.geojson"
            
        elif step_name == "tile":
            tile_index = kwargs.get('tile_index', 'H00_V00')
            return self.tile_dir / "tiles" / tile_index / "manifest.yml"
            
        else:
            raise ValueError(f"Unknown step name: {step_name}")
    
    def exists(self, step_name: str, **kwargs) -> bool:
        """Check if cached output exists for a step.
        
        Args:
            step_name: Name of the pipeline step
            **kwargs: Additional parameters for get_path()
            
        Returns:
            True if cache exists and is accessible
        """
        path = self.get_path(step_name, **kwargs)
        
        # For directories (like CRU timeseries)
        if step_name == "cru":
            return path.is_dir() and any(path.glob("*.nc"))
            
        return path.exists()
    
    def validate(self, step_name: str, **kwargs) -> bool:
        """Validate cached output can be opened/read.
        
        Args:
            step_name: Name of the pipeline step
            **kwargs: Additional parameters for get_path()
            
        Returns:
            True if cache is valid and readable
        """
        if not self.exists(step_name, **kwargs):
            return False
            
        path = self.get_path(step_name, **kwargs)
        
        try:
            if step_name in ["worldclim", "vegetation", "topography", "soil_texture", "fri"]:
                # Try opening NetCDF file
                with xr.open_dataset(path) as ds:
                    # Basic sanity check - has data variables
                    return len(ds.data_vars) > 0
                    
            elif step_name == "cru":
                # Check at least one file can be opened
                nc_files = list(path.glob("*.nc"))
                if not nc_files:
                    return False
                with xr.open_dataset(nc_files[0]) as ds:
                    return len(ds.data_vars) > 0
                    
            elif step_name in ["tile_index", "aoi_vector"]:
                # GeoJSON - just check it's valid JSON
                import json
                with open(path) as f:
                    data = json.load(f)
                return isinstance(data, dict)
                
            elif step_name == "tile":
                # YAML manifest
                with open(path) as f:
                    data = yaml.safe_load(f)
                return isinstance(data, dict) and 'index' in data
                
            elif step_name == "aoi_raster":
                # Try opening with rioxarray
                import rioxarray
                with rioxarray.open_rasterio(path) as ds:
                    return True
                    
            else:
                # Default: if file exists, consider it valid
                return True
                
        except Exception as e:
            # If we can't open/read it, it's not valid
            return False
    
    def invalidate(self, step_name: str, **kwargs) -> None:
        """Remove cached output for a step.
        
        Args:
            step_name: Name of the pipeline step
            **kwargs: Additional parameters for get_path()
        """
        path = self.get_path(step_name, **kwargs)
        
        if step_name == "cru" and path.is_dir():
            # Remove all files in directory
            import shutil
            if path.exists():
                shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    
    def get_all_steps(self) -> Dict[str, bool]:
        """Get cache status for all standard steps.
        
        Returns:
            Dictionary mapping step name to cache validity status
        """
        steps = [
            "aoi_vector",
            "aoi_raster", 
            "worldclim",
            "vegetation",
            "topography",
            "soil_texture",
            "fri",
            "cru",
            "tile_index"
        ]
        
        return {step: self.validate(step) for step in steps}
