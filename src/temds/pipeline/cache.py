"""Cache management for pipeline steps."""

from pathlib import Path
import shutil
from typing import Dict, List
import xarray as xr
import yaml
import geopandas as gpd


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
        self.export_dir = self.base_dir / f"04-{aoi_name}"
        
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

        elif step_name == "historic_explicit_fire":
            return self.data_dir / f"{self.aoi_name}_historic_explicit_fire.nc"

        elif step_name == "cru":
            return self.data_dir / f"{self.aoi_name}_cru"
            
        elif step_name == "setup_tiles":
            return self.tile_dir

        # if user passed the tile index, you get a path to that specific folder
        # otherwise you get the general path to the tiles forlder.
        elif step_name in ["process_tiles"]:
            tile_index = kwargs.get('tile_index', '')
            return self.tile_dir / "tiles" / tile_index

        elif step_name == "export_tiles":
            tile_index = kwargs.get('tile_index', '')
            return self.export_dir / "tiles" / tile_index

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
        
        # For directories (like CRU timeseries, or tiles...)
        if step_name == "cru":
            return path.is_dir() and any(path.glob("*.nc"))

        if step_name == "setup_tiles":
            # Check for tile index file and at least one tile directory with raster
            tile_index = path / "tile_index.geojson"
            has_tiles = path.is_dir() and any(path.glob("tiles/*/EPSG_6931.tiff"))
            return tile_index.exists() and has_tiles
        
        if step_name == "process_tiles":

            if not path.exists() or not path.is_dir():
                return False

            # Tile-specific path (`.../tiles/H01_V02`)
            tile_manifest = path / "manifest.yml"
            if tile_manifest.exists():
                return True

            # Container path (`.../tiles`) with multiple tile folders
            tile_dirs = list(path.glob("H*V*"))
            if not tile_dirs:
                return False
            return all((tile_dir / "manifest.yml").exists() for tile_dir in tile_dirs)

        return path.exists()
    
    def validate(self, step_name: str, **kwargs) -> bool:
        """Validate cached output can be opened/read.
        
        Args:
            step_name: Name of the pipeline step
            **kwargs: Additional parameters for get_path()
            
        Returns:
            True if cache is valid and readable
        """

        # this is the basic check to see that the files exist
        if not self.exists(step_name, **kwargs):
            return False
            
        path = self.get_path(step_name, **kwargs)
        
        # This is the more robust check to see that the data is readable...
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
                    
            elif step_name == "aoi_vector":
                # GeoJSON - just check it's valid JSON
                import json
                with open(path) as f:
                    data = json.load(f)
                return isinstance(data, dict)
                
            elif step_name == "aoi_raster":
                # Try opening with rioxarray
                import rioxarray
                with rioxarray.open_rasterio(path) as ds:
                    return True
            
            elif step_name == "setup_tiles":
                # Validate tile index GeoJSON and at least one tile raster
                import json
                tile_index_path = path / "tile_index.geojson"
                if not tile_index_path.exists():
                    return False
                
                # Check tile index is valid GeoJSON
                with open(tile_index_path) as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    return False
                
                # Check at least one tile raster exists and can be opened
                tile_rasters = list(path.glob("tiles/*/EPSG_6931.tiff"))
                if not tile_rasters:
                    return False
                
                # Try opening one tile raster to verify it's valid
                import rioxarray
                with rioxarray.open_rasterio(tile_rasters[0]) as ds:
                    return True

            elif step_name in ["process_tiles"]:

                # There is a lot of stuff to validate here:
                # 1. tile directory structure exists
                # 2. each tile directory has a manifest.yml
                # 3. each manifest.yml has the expected keys (e.g., 'data', 'cru-downscale')
                # 4. optionally, check that the expected output files listed in the manifest actually exist and can be opened.

                # three possibilities:
                # 1. tile is in cache with valid manifest -> skip
                # 2. tile is in cache but manifest is invalid -> re-process
                # 3. tile is not in cache at all -> process

                # Should make this operate on a single (passed in by kwarg) tile index.

                manifest_paths = []

                # Tile-specific path (`.../tiles/H01_V02`)
                tile_manifest = path / "manifest.yml"
                if tile_manifest.exists():
                    manifest_paths = [tile_manifest]
                else:
                    # Container path (`.../tiles`) with multiple tile folders
                    manifest_paths = [tile_dir / "manifest.yml" for tile_dir in path.glob("H*V*")]

                if not manifest_paths:
                    return False

                for manifest_path in manifest_paths:
                    if not manifest_path.exists():
                        return False
                    with open(manifest_path) as f:
                        manifest = yaml.safe_load(f) or {}
                    if 'data' not in manifest:
                        return False
                    if 'cru-downscaled' not in manifest['data']:
                        return False

                return True

            elif step_name == "export_tiles":
                # Similar to process_tiles, but we would check for the presence
                # of the final exported files (e.g., TEM input files) and that
                # they can be opened.
                return False

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
        
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
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
            "setup_tiles",
            "process_tiles",
            "export_tiles",
        ]
        
        return {step: self.validate(step) for step in steps}

    # def _tile_has_data(self, tile_idx: str, 
    #                required_datasets: List[str]) -> bool:
    #     """Check if tile has specific datasets in its manifest."""
    #     tile_dir = self.tile_dir / "tiles" / tile_idx
    #     manifest_path = tile_dir / "manifest.yml"
    
    #     if not manifest_path.exists():
    #         return False
    
    #     with open(manifest_path) as f:
    #         manifest = yaml.safe_load(f)
    
    #     return all(ds in manifest.get('data', {}) for ds in required_datasets)

    # def _load_tile_index(self):
    #     """Load tile index GeoDataFrame."""
    #     tile_dir = self.get_path("setup_tiles")
    #     tile_index_path = tile_dir / "tile_index.geojson"
    
    #     if not tile_index_path.exists():
    #         raise FileNotFoundError(f"Tile index not found. Run setup_tiles first.")
    
    #     return gpd.read_file(tile_index_path)

    # def _get_tiles_to_process(self, tile_index_gdf) -> List[str]:
    #     """Determine which tiles to process based on config."""
    #     if self.config.tile_config.tile_indices:
    #         return self.config.tile_config.tile_indices
    #     elif self.config.tile_config.all_tiles:
    #         return tile_index_gdf['tile_id'].tolist()
    #     else:
    #         return []
