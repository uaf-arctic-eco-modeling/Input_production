# Pipeline System

A repeatable, configurable pipeline for processing climate and environmental data with automatic caching and resume capabilities.

## Features

- **Automatic Caching**: Each step checks for cached outputs and skips re-processing when possible
- **Resume Capability**: Interrupted runs can be resumed from where they left off
- **Flexible Execution**: Run the full pipeline, specific steps, or step ranges
- **Multiple AOIs**: Process multiple Areas of Interest in a single run
- **Configuration-Based**: Define workflows in YAML for repeatability
- **Both CLI & API**: Use from command line or programmatically

## Quick Start

### 1. Create a Configuration File

```bash
# Generate a sample configuration
temds pipeline-init my-pipeline.yaml
```

Edit the generated file to specify your AOIs and data paths:

```yaml
aois:
  - name: my_study_area
    vector_file: working/01-aoi/my_study_area/my_study_area.geojson

working_dir: working
resolution: 1000
crs: EPSG:6931

data_sources:
  worldclim: working/00-download/worldclim
  vegetation: working/00-download/vegetation/
  topography: working/00-download/topo/
  soil_texture: working/00-download/soiltexture/
  fri: synthetic
```

### 2. Run the Pipeline

```bash
# Run full pipeline
temds pipeline-run my-pipeline.yaml

# Run for specific AOI only
temds pipeline-run my-pipeline.yaml --aoi my_study_area

# Run specific step only
temds pipeline-run my-pipeline.yaml --only-step worldclim

# Run from a step to the end
temds pipeline-run my-pipeline.yaml --from-step cru

# Force re-run everything (ignore cache)
temds pipeline-run my-pipeline.yaml --force-all
```

### 3. Check Pipeline Status

```bash
# List available steps
temds pipeline-list-steps

# Check what's already cached
temds pipeline-cache-status my-pipeline.yaml
```

## Pipeline Steps

The pipeline executes steps in this order:

1. **aoi_raster** - Convert AOI vector to raster format
2. **worldclim** - Load WorldClim climate data
3. **vegetation** - Load vegetation classification data
4. **topography** - Load topography/elevation data
5. **soil_texture** - Load soil texture data
6. **fri** - Load or generate FRI fire data
7. **cru** - Load CRU-JRA timeseries data
8. **setup_tiles** - Creates a folder hierarchy for all the tiles and a tile index vector file
9. **tiles** - Process individual tiles (optional)

Each step:
- Creates standardized outputs in `working/` directory
- Checks for cached data before running
- Can be enabled/disabled in configuration
- Can be forced to re-run

## Configuration Reference

### Basic Structure

```yaml
# List of AOIs to process
aois:
  - name: site1
    vector_file: path/to/site1.geojson
  - name: site2
    vector_file: path/to/site2.geojson

# Global settings
working_dir: working
resolution: 1000  # meters
crs: EPSG:6931    # projection

# Data source paths
data_sources:
  worldclim: path/to/worldclim
  vegetation: path/to/vegetation
  topography: path/to/topo
  soil_texture: path/to/soil
  fri: synthetic  # or path to data
  cru: path/to/cru  # optional

# Step configuration (optional)
steps:
  worldclim:
    enabled: true   # run this step
    force: false    # force re-run
    cache: true     # use caching

# Tile processing (optional)
tile_config:
  process_tiles: true
  tile_indices: ["H00_V00"]  # specific tiles
  all_tiles: false           # or process all
  baseline_start_year: 1970
  baseline_end_year: 2000
  downscale: true

# Logging (optional)
verbose: false
log_file: null  # or path to log file
```

### Step-by-Step Configuration

Control each step individually:

```yaml
steps:
  aoi_raster:
    enabled: true
    force: false
    cache: true
  
  worldclim:
    enabled: true
    force: true  # Force re-run even if cached
    cache: false # Don't cache outputs
  
  cru:
    enabled: false  # Skip this step entirely
```

## Programmatic Usage

Use the pipeline from Python code:

```python
from temds.pipeline import Pipeline
from temds.logger import Logger

# Create logger
logger = Logger(level='INFO')

# Load pipeline from config
pipeline = Pipeline.from_config_file('my-pipeline.yaml', logger=logger)

# Run everything
pipeline.run()

# Or with filters
pipeline.run(
    aoi_names=['site1'],
    from_step='worldclim',
    to_step='topography'
)
```

Create configuration programmatically:

```python
from temds.pipeline.config import PipelineConfig, AOIConfig, DataSourcePaths

config = PipelineConfig(
    aois=[
        AOIConfig(name="site1", vector_file="site1.geojson")
    ],
    working_dir="working",
    resolution=1000,
    data_sources=DataSourcePaths(
        worldclim="working/00-download/worldclim",
        vegetation="working/00-download/vegetation/",
        topography="working/00-download/topo/",
        soil_texture="working/00-download/soiltexture/",
        fri="synthetic"
    )
)

# Save to file
config.to_yaml('my-pipeline.yaml')

# Or use directly
pipeline = Pipeline(config)
pipeline.run()
```

## Cache Management

### How Caching Works

The pipeline automatically caches outputs at each step:

```
working/
├── 01-aoi/{aoi_name}/
│   ├── {aoi_name}.geojson        # AOI vector
│   └── {aoi_name}_6931_1000m.tiff # AOI raster
├── 02-{aoi_name}/
│   ├── {aoi_name}_wc_6931_1000m.nc  # WorldClim
│   ├── {aoi_name}_veg.nc            # Vegetation
│   ├── {aoi_name}_topo.nc           # Topography
│   ├── {aoi_name}_soiltex.nc        # Soil texture
│   ├── {aoi_name}_fri-fire.nc       # FRI fire
│   └── {aoi_name}_cru/              # CRU timeseries
│       ├── 1901.nc
│       ├── 1902.nc
│       └── ...
└── 03-{aoi_name}/
    └── tiles/
        ├── tile_index.geojson
        └── H00_V00/
            ├── manifest.yml
            ├── worldclim.nc
            └── ...
```

### Cache Status

Check what's already processed:

```bash
temds pipeline-cache-status my-pipeline.yaml
```

Output:
```
Cache status for AOI: site1
============================================================
  ✓ aoi_raster          working/01-aoi/site1/site1_6931_1000m.tiff
  ✓ worldclim           working/02-site1/site1_wc_6931_1000m.nc
  ✗ vegetation          (not cached)
  ✗ topography          (not cached)
  ...
```

### Clearing Cache

To force re-processing, either:

1. Use `--force-all` flag:
   ```bash
   temds pipeline-run my-pipeline.yaml --force-all
   ```

2. Configure step to force re-run:
   ```yaml
   steps:
     worldclim:
       force: true
   ```

3. Manually delete cached files:
   ```bash
   rm working/02-site1/site1_wc_6931_1000m.nc
   ```

## Examples

See the `examples/` directory for complete configurations:

- `pipeline_simple.yaml` - Minimal configuration
- `pipeline_temrs.yaml` - Full TEM-RS workflow with all options

## Migration from Legacy Scripts

Old manual script (150+ lines):
```python
for AOI_NAME in AOI_NAMES:
    aoi = AOIMask.load_vector(f"working/01-aoi/{AOI_NAME}.geojson")
    aoi.to_rasterfile(...)
    wc = TEMDataset.from_worldclim(...)
    wc.save(...)
    veg = TEMDataset.from_vegetation(...)
    veg.save(...)
    # ... many more manual steps
```

New pipeline approach (5 lines):
```python
from temds.pipeline import Pipeline

pipeline = Pipeline.from_config_file('pipeline.yaml')
pipeline.run()
```

Benefits:
- Automatic caching - no manual file existence checks
- Easy to resume interrupted runs
- Configuration separate from code
- Better logging and error handling
- Consistent file naming and organization

## Troubleshooting

### Step fails with "AOI raster not found"

Steps depend on previous steps. Make sure required steps are enabled and have run successfully.

### "Unknown step name" error

Check step name spelling. Use `temds pipeline-list-steps` to see valid step names.

### Cache not working

- Verify file permissions in `working_dir`
- Check that step has `cache: true` in configuration
- Ensure cached files are valid (pipeline validates NetCDF files)

### Out of memory

For large datasets:
- Process AOIs one at a time: `--aoi site1`
- Reduce tile size
- Check available disk space

## Advanced Usage

### Custom Step Ranges

Run steps 3-6 only:
```bash
temds pipeline-run config.yaml --from-step vegetation --to-step fri
```

### Multiple AOIs with Different Settings

Create separate config files per AOI or use multiple runs:

```bash
# Run just worldclim for all AOIs
temds pipeline-run config.yaml --only-step worldclim

# Then run rest for specific AOI
temds pipeline-run config.yaml --aoi site1 --from-step vegetation
```

### Tile Processing

Process specific tiles:
```yaml
tile_config:
  process_tiles: true
  tile_indices: ["H01_V01", "H01_V02", "H02_V01"]
  downscale: true
```

Or all tiles:
```yaml
tile_config:
  process_tiles: true
  all_tiles: true
```

### Verbose Logging

Get detailed execution information:
```bash
temds pipeline-run config.yaml --verbose
```

Or in config:
```yaml
verbose: true
log_file: pipeline.log  # Also save to file
```

## Testing

Run the pipeline tests:

```bash
pytest tests/test_pipeline.py -v
```

## Architecture

The pipeline consists of:

- **`pipeline/config.py`** - Pydantic configuration schema
- **`pipeline/cache.py`** - Cache management and validation
- **`pipeline/pipeline.py`** - Core execution engine with step decorator
- **`cli.py`** - Command-line interface (Typer)

Each step is a decorated method that:
1. Checks if step is enabled
2. Validates cached output
3. Runs if cache miss or forced
4. Updates statistics

## License

See main project LICENSE file.
