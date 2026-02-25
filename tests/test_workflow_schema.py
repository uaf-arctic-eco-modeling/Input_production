"""
Tests for workflow schema validation.
"""

import pytest
from pathlib import Path
from pydantic import ValidationError

from temds.workflow.schema import (
    WorkflowConfig,
    AOIConfig,
    DataSourceConfig,
    BaselineStepConfig,
    DownscaleStepConfig,
    TileStepConfig,
    IngestStepConfig,
    ExportConfig,
    validate_workflow_file,
    WorkflowValidationError,
)


def test_aoi_config_basic():
    """Test basic AOI configuration."""
    config = AOIConfig(
        source="test.shp",
        resolution=1000,
        crs="EPSG:6931"
    )
    assert config.source == "test.shp"
    assert config.resolution == 1000
    assert config.crs == "EPSG:6931"


def test_aoi_config_defaults():
    """Test AOI configuration with defaults."""
    config = AOIConfig(source="test.shp")
    assert config.resolution == 1000
    assert config.crs == "EPSG:6931"
    assert config.buffer is None


def test_aoi_config_validation_negative_resolution():
    """Test that negative resolution is rejected."""
    with pytest.raises(ValidationError):
        AOIConfig(source="test.shp", resolution=-1000)


def test_datasource_config_worldclim():
    """Test datasource config for WorldClim."""
    config = DataSourceConfig(
        name="wc",
        type="worldclim",
        version="2.1",
        cache="path/to/wc.nc"
    )
    assert config.name == "wc"
    assert config.type == "worldclim"
    assert config.version == "2.1"


def test_datasource_config_crujra():
    """Test datasource config for CRU-JRA."""
    config = DataSourceConfig(
        name="cru",
        type="crujra",
        years=[1901, 2023],
        cache="path/to/cru/"
    )
    assert config.years == [1901, 2023]


def test_datasource_config_invalid_years():
    """Test that invalid year ranges are rejected."""
    # Start year > end year
    with pytest.raises(ValidationError):
        DataSourceConfig(
            name="cru",
            type="crujra",
            years=[2023, 1901]
        )
    
    # Unrealistic years
    with pytest.raises(ValidationError):
        DataSourceConfig(
            name="cru",
            type="crujra",
            years=[1500, 1600]
        )


def test_baseline_step_config():
    """Test baseline step configuration."""
    config = BaselineStepConfig(
        name="baseline1",
        source="cru",
        years=[1970, 2000]
    )
    assert config.type == "baseline"
    assert config.name == "baseline1"
    assert config.years == [1970, 2000]


def test_downscale_step_config():
    """Test downscale step configuration."""
    config = DownscaleStepConfig(
        name="cru-downscaled",
        timeseries="cru",
        baseline="cru-baseline"
    )
    assert config.type == "downscale"
    assert config.additive is False  # Default


def test_tile_step_config():
    """Test tile step configuration."""
    config = TileStepConfig(
        tile_size=[100000, 100000],
        buffer_px=20
    )
    assert config.type == "tile"
    assert config.tile_size == [100000, 100000]
    assert config.buffer_px == 20


def test_export_config():
    """Test export configuration."""
    config = ExportConfig(
        format="TEM",
        output="working/05-tiles-TEM/"
    )
    assert config.format == "TEM"
    assert config.output == "working/05-tiles-TEM/"


def test_minimal_workflow_config():
    """Test minimal valid workflow configuration."""
    config = WorkflowConfig(
        name="test_workflow",
        aoi=AOIConfig(source="test.shp"),
        datasources=[],
        pipeline=[]
    )
    assert config.name == "test_workflow"
    assert len(config.datasources) == 0
    assert len(config.pipeline) == 0


def test_workflow_config_with_datasources():
    """Test workflow with datasources."""
    config = WorkflowConfig(
        name="test_workflow",
        aoi=AOIConfig(source="test.shp"),
        datasources=[
            DataSourceConfig(name="wc", type="worldclim"),
            DataSourceConfig(name="cru", type="crujra", years=[1901, 2023])
        ]
    )
    assert len(config.datasources) == 2
    assert config.get_datasource("wc").type == "worldclim"
    assert config.get_datasource("cru").type == "crujra"


def test_workflow_duplicate_datasource_names():
    """Test that duplicate datasource names are rejected."""
    with pytest.raises(ValidationError, match="Duplicate datasource names"):
        WorkflowConfig(
            name="test_workflow",
            aoi=AOIConfig(source="test.shp"),
            datasources=[
                DataSourceConfig(name="data", type="worldclim"),
                DataSourceConfig(name="data", type="crujra")  # Duplicate
            ]
        )


def test_workflow_step_reference_validation():
    """Test that steps can only reference existing datasources."""
    # This should fail - baseline references non-existent datasource
    with pytest.raises(ValidationError, match="unknown source"):
        WorkflowConfig(
            name="test_workflow",
            aoi=AOIConfig(source="test.shp"),
            datasources=[
                DataSourceConfig(name="wc", type="worldclim")
            ],
            pipeline=[
                BaselineStepConfig(
                    name="baseline1",
                    source="cru",  # Doesn't exist!
                    years=[1970, 2000]
                )
            ]
        )


def test_workflow_downscale_reference_validation():
    """Test that downscale steps validate references."""
    # This should fail - downscale references non-existent baseline
    with pytest.raises(ValidationError, match="unknown baseline"):
        WorkflowConfig(
            name="test_workflow",
            aoi=AOIConfig(source="test.shp"),
            datasources=[
                DataSourceConfig(name="cru", type="crujra", years=[1901, 2023])
            ],
            pipeline=[
                DownscaleStepConfig(
                    name="cru-ds",
                    timeseries="cru",
                    baseline="nonexistent-baseline"  # Doesn't exist!
                )
            ]
        )


def test_workflow_valid_pipeline_sequence():
    """Test a valid pipeline with proper dependency chain."""
    config = WorkflowConfig(
        name="test_workflow",
        aoi=AOIConfig(source="test.shp"),
        datasources=[
            DataSourceConfig(name="wc", type="worldclim"),
            DataSourceConfig(name="cru", type="crujra", years=[1901, 2023])
        ],
        pipeline=[
            IngestStepConfig(datasources=["wc", "cru"]),
            BaselineStepConfig(
                name="cru-baseline",
                source="cru",
                years=[1970, 2000]
            ),
            DownscaleStepConfig(
                name="cru-downscaled",
                timeseries="cru",
                baseline="cru-baseline"
            )
        ]
    )
    # Should not raise - all references are valid
    assert len(config.pipeline) == 3


def test_workflow_from_yaml(tmp_path):
    """Test loading workflow from YAML file."""
    yaml_content = """
workflow:
  name: "test_workflow"
  aoi:
    source: "test.shp"
    resolution: 1000
    crs: "EPSG:6931"
  datasources:
    - name: wc
      type: worldclim
      version: "2.1"
"""
    yaml_file = tmp_path / "test_workflow.yaml"
    yaml_file.write_text(yaml_content)
    
    config = WorkflowConfig.from_yaml(yaml_file)
    assert config.name == "test_workflow"
    assert config.aoi.source == "test.shp"
    assert len(config.datasources) == 1


def test_workflow_to_yaml(tmp_path):
    """Test saving workflow to YAML file."""
    config = WorkflowConfig(
        name="test_workflow",
        aoi=AOIConfig(source="test.shp"),
        datasources=[
            DataSourceConfig(name="wc", type="worldclim")
        ]
    )
    
    yaml_file = tmp_path / "output.yaml"
    config.to_yaml(yaml_file)
    
    # Load it back and verify
    loaded = WorkflowConfig.from_yaml(yaml_file)
    assert loaded.name == config.name
    assert loaded.aoi.source == config.aoi.source


def test_validate_workflow_file_success(tmp_path):
    """Test workflow file validation success."""
    yaml_content = """
workflow:
  name: "test"
  aoi:
    source: "test.shp"
"""
    yaml_file = tmp_path / "valid.yaml"
    yaml_file.write_text(yaml_content)
    
    # Should not raise
    config = validate_workflow_file(yaml_file)
    assert config.name == "test"


def test_validate_workflow_file_failure(tmp_path):
    """Test workflow file validation failure."""
    yaml_content = """
workflow:
  name: "test"
  # Missing required 'aoi' field
  datasources: []
"""
    yaml_file = tmp_path / "invalid.yaml"
    yaml_file.write_text(yaml_content)
    
    with pytest.raises(WorkflowValidationError):
        validate_workflow_file(yaml_file)


def test_example_workflows_are_valid():
    """Test that example workflow files are valid."""
    examples_dir = Path(__file__).parent.parent.parent / "examples"
    
    if not examples_dir.exists():
        pytest.skip("Examples directory not found")
    
    yaml_files = list(examples_dir.glob("workflow_*.yaml"))
    
    if not yaml_files:
        pytest.skip("No example workflow files found")
    
    for yaml_file in yaml_files:
        # Should not raise validation errors
        try:
            config = validate_workflow_file(yaml_file)
            assert config.name is not None
        except WorkflowValidationError as e:
            pytest.fail(f"Example workflow {yaml_file.name} failed validation: {e}")
