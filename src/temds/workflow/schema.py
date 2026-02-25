"""
Workflow schema definitions using Pydantic for validation.

This module defines the data models for declarative workflow configuration
in YAML files. Pydantic provides validation, type checking, and automatic
documentation generation.
"""

from typing import Optional, List, Dict, Any, Literal, Union
from pathlib import Path
from pydantic import BaseModel, Field, field_validator, model_validator
import yaml


class AOIConfig(BaseModel):
    """Configuration for Area of Interest."""
    
    source: str = Field(
        ...,
        description="Path to AOI file (shapefile, GeoJSON, or raster)"
    )
    
    resolution: int = Field(
        default=1000,
        description="Resolution in CRS units (typically meters)",
        gt=0
    )
    
    crs: str = Field(
        default="EPSG:6931",
        description="Coordinate Reference System (EPSG code or PROJ4 string)"
    )
    
    buffer: Optional[int] = Field(
        default=None,
        description="Buffer distance in CRS units",
        ge=0
    )
    
    @field_validator('source')
    @classmethod
    def source_must_exist_or_be_creatable(cls, v):
        """Validate source path."""
        # Note: Don't enforce existence at parse time since file might be created
        # during workflow execution. This is just a basic format check.
        if not v:
            raise ValueError("AOI source cannot be empty")
        return v


class DataSourceConfig(BaseModel):
    """Configuration for a data source."""
    
    name: str = Field(
        ...,
        description="Unique name for this datasource in the workflow"
    )
    
    type: Literal[
        'worldclim',
        'crujra',
        'cmip6',
        'era5',
        'vegetation',
        'topo',
        'soil_texture',
        'fri',
        'historic_ef'
    ] = Field(
        ...,
        description="Type of data source"
    )
    
    version: Optional[str] = Field(
        None,
        description="Version of the dataset (e.g., '2.1' for WorldClim)"
    )
    
    years: Optional[List[int]] = Field(
        None,
        description="Year range for time series data [start_year, end_year]",
        min_length=2,
        max_length=2
    )
    
    download: bool = Field(
        default=False,
        description="Whether to download data if not cached"
    )
    
    cache: Optional[str] = Field(
        None,
        description="Path to cache file/directory for this datasource"
    )
    
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional datasource-specific options"
    )
    
    @field_validator('years')
    @classmethod
    def years_must_be_ordered(cls, v):
        """Ensure year range is valid."""
        if v is not None and len(v) == 2:
            if v[0] > v[1]:
                raise ValueError(f"Start year {v[0]} must be <= end year {v[1]}")
            if v[0] < 1800 or v[1] > 2100:
                raise ValueError(f"Year range {v} seems unrealistic")
        return v


class BaselineStepConfig(BaseModel):
    """Configuration for baseline calculation step."""
    
    type: Literal['baseline'] = 'baseline'
    name: str = Field(..., description="Name for this baseline (e.g., 'cru-baseline')")
    source: str = Field(..., description="Name of timeseries datasource")
    years: List[int] = Field(..., description="[start_year, end_year] for baseline")
    
    @field_validator('years')
    @classmethod
    def validate_baseline_years(cls, v):
        if len(v) != 2:
            raise ValueError("Baseline years must be [start_year, end_year]")
        if v[0] > v[1]:
            raise ValueError("Start year must be <= end year")
        return v


class DownscaleStepConfig(BaseModel):
    """Configuration for downscaling step."""
    
    type: Literal['downscale'] = 'downscale'
    name: str = Field(..., description="Name for downscaled output")
    timeseries: str = Field(..., description="Name of timeseries to downscale")
    baseline: str = Field(..., description="Name of baseline to use")
    reference: Optional[str] = Field(
        None,
        description="Name of reference dataset (defaults to baseline)"
    )
    variables: Optional[List[str]] = Field(
        None,
        description="Variables to downscale (default: all safe variables)"
    )
    additive: bool = Field(
        default=False,
        description="Use additive vs multiplicative correction"
    )


class TileStepConfig(BaseModel):
    """Configuration for tiling step."""
    
    type: Literal['tile'] = 'tile'
    tile_size: List[int] = Field(
        ...,
        description="[width, height] of tiles in CRS units",
        min_length=2,
        max_length=2
    )
    buffer_px: int = Field(
        default=20,
        description="Buffer in pixels around each tile",
        ge=0
    )
    nickname: Optional[str] = Field(
        None,
        description="Optional nickname for tile set"
    )


class IngestStepConfig(BaseModel):
    """Configuration for data ingestion step."""
    
    type: Literal['ingest'] = 'ingest'
    datasources: List[str] = Field(
        ...,
        description="List of datasource names to ingest"
    )


class ExportConfig(BaseModel):
    """Configuration for export."""
    
    format: Literal['TEM', 'raw', 'netcdf'] = Field(
        default='TEM',
        description="Export format"
    )
    
    output: str = Field(
        ...,
        description="Output directory path"
    )
    
    datasets: Optional[List[str]] = Field(
        None,
        description="Which datasets to export (default: all)"
    )
    
    options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Format-specific export options"
    )


class WorkflowConfig(BaseModel):
    """
    Complete workflow configuration.
    
    This is the top-level schema for workflow YAML files.
    
    Example
    -------
    ```yaml
    workflow:
      name: "toolik_site"
      aoi:
        source: "working/01-aoi/toolik.shp"
        resolution: 1000
        crs: "EPSG:6931"
      datasources:
        - name: worldclim
          type: worldclim
          version: "2.1"
          cache: "working/02-toolik/wc.nc"
        - name: cru
          type: crujra
          years: [1901, 2023]
          cache: "working/02-toolik/cru/"
      pipeline:
        - type: ingest
          datasources: [worldclim, cru]
        - type: baseline
          name: cru-baseline
          source: cru
          years: [1970, 2000]
        - type: downscale
          name: cru-downscaled
          timeseries: cru
          baseline: cru-baseline
      export:
        format: TEM
        output: "working/05-tiles-TEM/"
    ```
    """
    
    name: str = Field(
        ...,
        description="Workflow name (used for logging and identification)"
    )
    
    description: Optional[str] = Field(
        None,
        description="Optional description of the workflow"
    )
    
    aoi: AOIConfig = Field(
        ...,
        description="Area of Interest configuration"
    )
    
    datasources: List[DataSourceConfig] = Field(
        default_factory=list,
        description="Data sources to use in workflow"
    )
    
    pipeline: List[Union[
        BaselineStepConfig,
        DownscaleStepConfig,
        TileStepConfig,
        IngestStepConfig
    ]] = Field(
        default_factory=list,
        description="Ordered list of processing steps"
    )
    
    export: Optional[ExportConfig] = Field(
        None,
        description="Export configuration"
    )
    
    working_dir: str = Field(
        default="working",
        description="Root working directory for intermediate files"
    )
    
    @field_validator('datasources')
    @classmethod
    def datasource_names_unique(cls, v):
        """Ensure datasource names are unique."""
        names = [ds.name for ds in v]
        if len(names) != len(set(names)):
            duplicates = [name for name in names if names.count(name) > 1]
            raise ValueError(f"Duplicate datasource names: {set(duplicates)}")
        return v
    
    @model_validator(mode='after')
    def validate_step_references(self):
        """Validate that steps reference existing datasources and previous steps."""
        datasources = {ds.name for ds in values.get('datasources', [])}
        pipeline = values.get('pipeline', [])
        
        # Track names created by previous steps
        available_names = datasources.copy()
        
        for step in pipeline:
            if isinstance(step, IngestStepConfig):
                # Check that referenced datasources exist
                for ds_name in step.datasources:
                    if ds_name not in datasources:
                        raise ValueError(
                            f"Ingest step references unknown datasource: {ds_name}"
                        )
            
            elif isinstance(step, BaselineStepConfig):
                # Check that source exists
                if step.source not in available_names:
                    raise ValueError(
                        f"Baseline step references unknown source: {step.source}"
                    )
                # Add baseline name to available names
                available_names.add(step.name)
            
            elif isinstance(step, DownscaleStepConfig):
                # Check timeseries and baseline exist
                if step.timeseries not in available_names:
                    raise ValueError(
                        f"Downscale step references unknown timeseries: {step.timeseries}"
                    )
                if step.baseline not in available_names:
                    raise ValueError(
                        f"Downscale step references unknown baseline: {step.baseline}"
                    )
                # Add downscaled name to available
                available_names.add(step.name)
        
        return self
    
    @classmethod
    def from_yaml(cls, path: Union[str, Path]) -> 'WorkflowConfig':
        """
        Load workflow configuration from YAML file.
        
        Parameters
        ----------
        path : str or Path
            Path to YAML file
            
        Returns
        -------
        WorkflowConfig
            Parsed and validated configuration
            
        Raises
        ------
        ValidationError
            If YAML doesn't match schema
        """
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        
        # Handle nested 'workflow' key if present
        if 'workflow' in data:
            data = data['workflow']
        
        return cls(**data)
    
    def to_yaml(self, path: Union[str, Path]):
        """
        Save workflow configuration to YAML file.
        
        Parameters
        ----------
        path : str or Path
            Output path
        """
        with open(path, 'w') as f:
            # Wrap in 'workflow' key for consistency
            yaml.dump(
                {'workflow': self.dict(exclude_none=True)},
                f,
                default_flow_style=False,
                sort_keys=False
            )
    
    def get_datasource(self, name: str) -> Optional[DataSourceConfig]:
        """Get datasource configuration by name."""
        for ds in self.datasources:
            if ds.name == name:
                return ds
        return None


class WorkflowValidationError(Exception):
    """Raised when workflow validation fails."""
    pass


def validate_workflow_file(path: Union[str, Path]) -> WorkflowConfig:
    """
    Validate a workflow YAML file.
    
    Parameters
    ----------
    path : str or Path
        Path to YAML file
        
    Returns
    -------
    WorkflowConfig
        Validated configuration
        
    Raises
    ------
    WorkflowValidationError
        If validation fails
    """
    try:
        return WorkflowConfig.from_yaml(path)
    except Exception as e:
        raise WorkflowValidationError(f"Workflow validation failed: {e}") from e
