"""Pipeline configuration schema."""

from typing import List, Optional, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field, field_validator


class DataSourcePaths(BaseModel):
    """Paths to data sources."""
    worldclim: Optional[str] = Field(None, description="Path to WorldClim data directory")
    vegetation: Optional[str] = Field(None, description="Path to vegetation data")
    topography: Optional[str] = Field(None, description="Path to topography data")
    soil_texture: Optional[str] = Field(None, description="Path to soil texture data")
    fri: Optional[str] = Field(None, description="Path to FRI data (or 'synthetic' to generate)")
    cru: Optional[str] = Field(None, description="Path to CRU-JRA data directory")


class StepConfig(BaseModel):
    """Configuration for individual pipeline steps."""
    enabled: bool = Field(True, description="Whether this step should run")
    force: bool = Field(False, description="Force re-run even if cache exists")
    cache: bool = Field(True, description="Use caching for this step")


class AOIConfig(BaseModel):
    """Configuration for an Area of Interest."""
    name: str = Field(..., description="Name of the AOI")
    vector_file: str = Field(..., description="Path to AOI vector file (GeoJSON, shapefile, etc.)")


class TileConfig(BaseModel):
    """Configuration for tile processing."""
    process_tiles: bool = Field(False, description="Whether to process individual tiles")
    tile_indices: Optional[List[str]] = Field(None, description="Specific tile indices to process (e.g., ['H01_V02'])")
    all_tiles: bool = Field(False, description="Process all tiles in the index")
    baseline_start_year: int = Field(1901, description="Start year for baseline calculation")
    baseline_end_year: int = Field(1930, description="End year for baseline calculation")
    downscale: bool = Field(True, description="Whether to perform downscaling")


class PipelineConfig(BaseModel):
    """Main pipeline configuration."""
    
    # AOIs to process
    aois: List[AOIConfig] = Field(..., description="List of AOIs to process")
    
    # Global settings
    working_dir: str = Field("working", description="Base working directory for outputs")
    resolution: int = Field(1000, description="Spatial resolution in meters")
    crs: str = Field("EPSG:6931", description="Coordinate reference system")
    
    # Data source paths
    data_sources: DataSourcePaths = Field(default_factory=DataSourcePaths, description="Paths to input data")
    
    # Step configuration
    steps: Dict[str, StepConfig] = Field(
        default_factory=lambda: {
            "aoi_raster": StepConfig(),
            "worldclim": StepConfig(),
            "vegetation": StepConfig(),
            "topography": StepConfig(),
            "soil_texture": StepConfig(),
            "fri": StepConfig(),
            "cru": StepConfig(),
            "tile_index": StepConfig(),
            "tiles": StepConfig(),
        },
        description="Configuration for each pipeline step"
    )
    
    # Tile processing configuration
    tile_config: TileConfig = Field(default_factory=TileConfig, description="Tile processing configuration")
    
    # Logging
    verbose: bool = Field(False, description="Enable verbose logging")
    log_file: Optional[str] = Field(None, description="Path to log file")
    
    @field_validator('working_dir', 'data_sources')
    @classmethod
    def expand_paths(cls, v):
        """Expand user paths in configuration."""
        if isinstance(v, str):
            return str(Path(v).expanduser())
        elif isinstance(v, DataSourcePaths):
            for field in ['worldclim', 'vegetation', 'topography', 'soil_texture', 'fri', 'cru']:
                value = getattr(v, field)
                if value and isinstance(value, str):
                    setattr(v, field, str(Path(value).expanduser()))
        return v
    
    @classmethod
    def from_yaml(cls, yaml_path: str | Path) -> "PipelineConfig":
        """Load configuration from YAML file.
        
        Args:
            yaml_path: Path to YAML configuration file
            
        Returns:
            PipelineConfig instance
        """
        import yaml
        
        with open(yaml_path) as f:
            config_dict = yaml.safe_load(f)
        
        return cls(**config_dict)
    
    def to_yaml(self, yaml_path: str | Path) -> None:
        """Save configuration to YAML file.
        
        Args:
            yaml_path: Path to save YAML configuration
        """
        import yaml
        
        with open(yaml_path, 'w') as f:
            yaml.dump(self.model_dump(), f, default_flow_style=False, sort_keys=False)
    
    def get_step_config(self, step_name: str) -> StepConfig:
        """Get configuration for a specific step.
        
        Args:
            step_name: Name of the step
            
        Returns:
            StepConfig for the step, or default if not configured
        """
        return self.steps.get(step_name, StepConfig())
    
    def is_step_enabled(self, step_name: str) -> bool:
        """Check if a step is enabled.
        
        Args:
            step_name: Name of the step
            
        Returns:
            True if step is enabled
        """
        return self.get_step_config(step_name).enabled
