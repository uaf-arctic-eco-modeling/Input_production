"""Tests for pipeline module."""

import pytest
import tempfile
from pathlib import Path
import yaml
import xarray as xr
import numpy as np

from temds.pipeline.cache import CacheManager
from temds.pipeline.config import PipelineConfig, AOIConfig, DataSourcePaths, StepConfig, TileConfig


class TestCacheManager:
    """Tests for CacheManager class."""
    
    def test_init(self, tmp_path):
        """Test CacheManager initialization."""
        cache = CacheManager(tmp_path, "test_aoi", resolution=1000, crs="EPSG:6931")
        
        assert cache.base_dir == tmp_path
        assert cache.aoi_name == "test_aoi"
        assert cache.resolution == 1000
        assert cache.crs == "EPSG:6931"
        assert cache.aoi_dir == tmp_path / "01-aoi" / "test_aoi"
        assert cache.data_dir == tmp_path / "02-test_aoi"
        assert cache.tile_dir == tmp_path / "03-test_aoi"
    
    def test_get_path_aoi_vector(self, tmp_path):
        """Test get_path for AOI vector."""
        cache = CacheManager(tmp_path, "test_aoi")
        path = cache.get_path("aoi_vector")
        
        assert path == tmp_path / "01-aoi" / "test_aoi" / "test_aoi.geojson"
    
    def test_get_path_aoi_raster(self, tmp_path):
        """Test get_path for AOI raster."""
        cache = CacheManager(tmp_path, "test_aoi", resolution=1000, crs="EPSG:6931")
        path = cache.get_path("aoi_raster")
        
        assert path == tmp_path / "01-aoi" / "test_aoi" / "test_aoi_6931_1000m.tiff"
    
    def test_get_path_worldclim(self, tmp_path):
        """Test get_path for WorldClim data."""
        cache = CacheManager(tmp_path, "test_aoi", resolution=1000, crs="EPSG:6931")
        path = cache.get_path("worldclim")
        
        assert path == tmp_path / "02-test_aoi" / "test_aoi_wc_6931_1000m.nc"
    
    def test_get_path_cru(self, tmp_path):
        """Test get_path for CRU timeseries."""
        cache = CacheManager(tmp_path, "test_aoi")
        path = cache.get_path("cru")
        
        assert path == tmp_path / "02-test_aoi" / "test_aoi_cru"
    
    def test_get_path_process_tiles(self, tmp_path):
        """Test get_path for process_tiles tile directory."""
        cache = CacheManager(tmp_path, "test_aoi")
        path = cache.get_path("process_tiles", tile_index="H01_V02")

        assert path == tmp_path / "03-test_aoi" / "tiles" / "H01_V02"
    
    def test_get_path_invalid_step(self, tmp_path):
        """Test get_path with invalid step name."""
        cache = CacheManager(tmp_path, "test_aoi")
        
        with pytest.raises(ValueError, match="Unknown step name"):
            cache.get_path("invalid_step")
    
    def test_exists_false(self, tmp_path):
        """Test exists returns False for non-existent file."""
        cache = CacheManager(tmp_path, "test_aoi")
        
        assert not cache.exists("worldclim")
    
    def test_exists_true(self, tmp_path):
        """Test exists returns True for existing file."""
        cache = CacheManager(tmp_path, "test_aoi")
        
        # Create a dummy file
        wc_path = cache.get_path("worldclim")
        wc_path.parent.mkdir(parents=True, exist_ok=True)
        wc_path.touch()
        
        assert cache.exists("worldclim")
    
    def test_exists_cru_directory(self, tmp_path):
        """Test exists for CRU directory with files."""
        cache = CacheManager(tmp_path, "test_aoi")
        
        cru_path = cache.get_path("cru")
        cru_path.mkdir(parents=True, exist_ok=True)
        
        # Empty directory - should be False
        assert not cache.exists("cru")
        
        # With a file - should be True
        (cru_path / "1901.nc").touch()
        assert cache.exists("cru")

    def test_exists_process_tiles_tile_directory(self, tmp_path):
        """Test exists for a processed tile directory."""
        cache = CacheManager(tmp_path, "test_aoi")

        tile_path = cache.get_path("process_tiles", tile_index="H01_V02")
        tile_path.mkdir(parents=True, exist_ok=True)
        assert not cache.exists("process_tiles", tile_index="H01_V02")

        (tile_path / "manifest.yml").write_text("data:\n  cru-downscaled: output.nc\n")
        assert cache.exists("process_tiles", tile_index="H01_V02")
    
    def test_validate_netcdf(self, tmp_path):
        """Test validate for NetCDF file."""
        cache = CacheManager(tmp_path, "test_aoi")
        
        # Create valid NetCDF
        wc_path = cache.get_path("worldclim")
        wc_path.parent.mkdir(parents=True, exist_ok=True)
        
        ds = xr.Dataset({
            'tair': (['y', 'x'], np.random.rand(10, 10)),
        })
        ds.to_netcdf(wc_path)
        
        assert cache.validate("worldclim")
    
    def test_validate_invalid_netcdf(self, tmp_path):
        """Test validate returns False for invalid NetCDF."""
        cache = CacheManager(tmp_path, "test_aoi")
        
        # Create invalid file
        wc_path = cache.get_path("worldclim")
        wc_path.parent.mkdir(parents=True, exist_ok=True)
        wc_path.write_text("not a netcdf file")
        
        assert not cache.validate("worldclim")

    def test_validate_process_tiles_manifest(self, tmp_path):
        """Test validate for process_tiles with valid manifest."""
        cache = CacheManager(tmp_path, "test_aoi")

        tile_path = cache.get_path("process_tiles", tile_index="H01_V02")
        tile_path.mkdir(parents=True, exist_ok=True)
        (tile_path / "manifest.yml").write_text(
            "data:\n"
            "  cru-downscaled: output.nc\n"
        )

        assert cache.validate("process_tiles", tile_index="H01_V02")
    
    def test_invalidate(self, tmp_path):
        """Test invalidate removes cached file."""
        cache = CacheManager(tmp_path, "test_aoi")
        
        # Create a file
        wc_path = cache.get_path("worldclim")
        wc_path.parent.mkdir(parents=True, exist_ok=True)
        wc_path.touch()
        
        assert wc_path.exists()
        
        # Invalidate
        cache.invalidate("worldclim")
        
        assert not wc_path.exists()

    def test_invalidate_process_tiles_directory(self, tmp_path):
        """Test invalidate removes processed tile directory."""
        cache = CacheManager(tmp_path, "test_aoi")

        tile_path = cache.get_path("process_tiles", tile_index="H01_V02")
        tile_path.mkdir(parents=True, exist_ok=True)
        (tile_path / "manifest.yml").write_text("data:\n  cru-downscaled: output.nc\n")

        assert tile_path.exists()
        cache.invalidate("process_tiles", tile_index="H01_V02")
        assert not tile_path.exists()
    
    def test_get_all_steps(self, tmp_path):
        """Test get_all_steps returns status dict."""
        cache = CacheManager(tmp_path, "test_aoi")
        
        # Create some valid files
        wc_path = cache.get_path("worldclim")
        wc_path.parent.mkdir(parents=True, exist_ok=True)
        ds = xr.Dataset({'tair': (['y', 'x'], np.random.rand(10, 10))})
        ds.to_netcdf(wc_path)
        
        status = cache.get_all_steps()
        
        assert isinstance(status, dict)
        assert "worldclim" in status
        assert status["worldclim"] is True  # Valid file exists
        assert status["vegetation"] is False  # Doesn't exist


class TestPipelineConfig:
    """Tests for PipelineConfig class."""
    
    def test_minimal_config(self):
        """Test creating minimal config."""
        config = PipelineConfig(
            aois=[
                AOIConfig(name="test", vector_file="test.geojson")
            ]
        )
        
        assert len(config.aois) == 1
        assert config.aois[0].name == "test"
        assert config.working_dir == "working"
        assert config.resolution == 1000
        assert config.crs == "EPSG:6931"
    
    def test_full_config(self):
        """Test creating full config with all options."""
        config = PipelineConfig(
            aois=[
                AOIConfig(name="test1", vector_file="test1.geojson"),
                AOIConfig(name="test2", vector_file="test2.geojson"),
            ],
            working_dir="/tmp/working",
            resolution=500,
            crs="EPSG:4326",
            data_sources=DataSourcePaths(
                worldclim="/data/worldclim",
                vegetation="/data/veg",
            ),
            steps={
                "worldclim": StepConfig(enabled=False, force=True),
            },
            tile_config=TileConfig(
                process_tiles=True,
                tile_indices=["H01_V01"],
                baseline_start_year=1950,
            ),
            verbose=True,
        )
        
        assert len(config.aois) == 2
        assert config.resolution == 500
        assert config.crs == "EPSG:4326"
        assert config.data_sources.worldclim == "/data/worldclim"
        assert config.tile_config.baseline_start_year == 1950
        assert config.verbose is True
    
    def test_get_step_config(self):
        """Test getting step configuration."""
        config = PipelineConfig(
            aois=[AOIConfig(name="test", vector_file="test.geojson")],
            steps={
                "worldclim": StepConfig(enabled=False, force=True),
            }
        )
        
        # Configured step
        wc_config = config.get_step_config("worldclim")
        assert wc_config.enabled is False
        assert wc_config.force is True
        
        # Unconfigured step (returns default)
        veg_config = config.get_step_config("vegetation")
        assert veg_config.enabled is True
        assert veg_config.force is False
    
    def test_is_step_enabled(self):
        """Test checking if step is enabled."""
        config = PipelineConfig(
            aois=[AOIConfig(name="test", vector_file="test.geojson")],
            steps={
                "worldclim": StepConfig(enabled=False),
                "vegetation": StepConfig(enabled=True),
            }
        )
        
        assert not config.is_step_enabled("worldclim")
        assert config.is_step_enabled("vegetation")
        assert config.is_step_enabled("topography")  # Default is enabled
    
    def test_to_yaml_and_from_yaml(self, tmp_path):
        """Test saving and loading config from YAML."""
        config = PipelineConfig(
            aois=[
                AOIConfig(name="test", vector_file="test.geojson")
            ],
            resolution=2000,
            verbose=True,
        )
        
        yaml_path = tmp_path / "config.yaml"
        config.to_yaml(yaml_path)
        
        assert yaml_path.exists()
        
        # Load it back
        loaded_config = PipelineConfig.from_yaml(yaml_path)
        
        assert loaded_config.aois[0].name == "test"
        assert loaded_config.resolution == 2000
        assert loaded_config.verbose is True
    
    def test_yaml_content(self, tmp_path):
        """Test YAML content is readable."""
        config = PipelineConfig(
            aois=[
                AOIConfig(name="test", vector_file="test.geojson")
            ],
        )
        
        yaml_path = tmp_path / "config.yaml"
        config.to_yaml(yaml_path)
        
        # Read YAML and check structure
        with open(yaml_path) as f:
            yaml_data = yaml.safe_load(f)
        
        assert "aois" in yaml_data
        assert len(yaml_data["aois"]) == 1
        assert yaml_data["aois"][0]["name"] == "test"
        assert "working_dir" in yaml_data
        assert "resolution" in yaml_data


class TestPipelineStepFilters:
    """Tests for pipeline step filtering logic."""
    
    def test_get_steps_to_run_all(self):
        """Test getting all steps."""
        from temds.pipeline.pipeline import Pipeline
        from temds.logger import Logger
        
        config = PipelineConfig(
            aois=[AOIConfig(name="test", vector_file="test.geojson")]
        )
        pipeline = Pipeline(config, Logger())
        
        steps = pipeline._get_steps_to_run(None, None, None)
        
        assert steps == Pipeline.STEP_ORDER
    
    def test_get_steps_to_run_from_step(self):
        """Test getting steps from a starting point."""
        from temds.pipeline.pipeline import Pipeline
        from temds.logger import Logger
        
        config = PipelineConfig(
            aois=[AOIConfig(name="test", vector_file="test.geojson")]
        )
        pipeline = Pipeline(config, Logger())
        
        steps = pipeline._get_steps_to_run(from_step="worldclim", to_step=None, only_step=None)
        
        assert "aoi_raster" not in steps
        assert "worldclim" in steps
        assert steps[0] == "worldclim"
    
    def test_get_steps_to_run_to_step(self):
        """Test getting steps up to an endpoint."""
        from temds.pipeline.pipeline import Pipeline
        from temds.logger import Logger
        
        config = PipelineConfig(
            aois=[AOIConfig(name="test", vector_file="test.geojson")]
        )
        pipeline = Pipeline(config, Logger())
        
        steps = pipeline._get_steps_to_run(from_step=None, to_step="vegetation", only_step=None)
        
        assert "vegetation" in steps
        assert "topography" not in steps
        assert steps[-1] == "vegetation"
    
    def test_get_steps_to_run_range(self):
        """Test getting steps in a range."""
        from temds.pipeline.pipeline import Pipeline
        from temds.logger import Logger
        
        config = PipelineConfig(
            aois=[AOIConfig(name="test", vector_file="test.geojson")]
        )
        pipeline = Pipeline(config, Logger())
        
        steps = pipeline._get_steps_to_run(from_step="worldclim", to_step="topography", only_step=None)
        
        assert "aoi_raster" not in steps
        assert "worldclim" in steps
        assert "vegetation" in steps
        assert "topography" in steps
        assert "soil_texture" not in steps
    
    def test_get_steps_to_run_only_step(self):
        """Test getting only a specific step."""
        from temds.pipeline.pipeline import Pipeline
        from temds.logger import Logger
        
        config = PipelineConfig(
            aois=[AOIConfig(name="test", vector_file="test.geojson")]
        )
        pipeline = Pipeline(config, Logger())
        
        steps = pipeline._get_steps_to_run(from_step=None, to_step=None, only_step="worldclim")
        
        assert steps == ["worldclim"]
    
    def test_get_steps_to_run_invalid_step(self):
        """Test error on invalid step name."""
        from temds.pipeline.pipeline import Pipeline
        from temds.logger import Logger
        
        config = PipelineConfig(
            aois=[AOIConfig(name="test", vector_file="test.geojson")]
        )
        pipeline = Pipeline(config, Logger())
        
        with pytest.raises(ValueError, match="Unknown step"):
            pipeline._get_steps_to_run(from_step="invalid_step", to_step=None, only_step=None)


class TestPipelineIntegration:
    """Integration tests for pipeline."""
    
    def test_pipeline_from_config_file(self, tmp_path):
        """Test creating pipeline from config file."""
        from temds.pipeline.pipeline import Pipeline
        
        # Create a config file
        config = PipelineConfig(
            aois=[AOIConfig(name="test", vector_file="test.geojson")],
            working_dir=str(tmp_path),
        )
        
        config_path = tmp_path / "config.yaml"
        config.to_yaml(config_path)
        
        # Load pipeline from file
        pipeline = Pipeline.from_config_file(config_path)
        
        assert pipeline.config.aois[0].name == "test"
        assert pipeline.config.working_dir == str(tmp_path)
    
    def test_pipeline_stats_initialization(self):
        """Test pipeline statistics are initialized."""
        from temds.pipeline.pipeline import Pipeline
        
        config = PipelineConfig(
            aois=[AOIConfig(name="test", vector_file="test.geojson")]
        )
        pipeline = Pipeline(config)
        
        assert pipeline.stats['steps_run'] == 0
        assert pipeline.stats['steps_cached'] == 0
        assert pipeline.stats['steps_skipped'] == 0
        assert pipeline.stats['aois_processed'] == 0
