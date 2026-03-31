import typer
from typing_extensions import Annotated
from typing import Literal, List, Optional

from . import subprograms
from .pipeline import Pipeline
import temds
import temds.logger


VALID_SUBPROGRAMS = Literal['download', 'preprocess', 'setup']

app = typer.Typer()

@app.command()
def bucketfill_cru():
    print("need to implement this. Call all the bucket filling functions using "
          "CloudShellBucketFiller?")
    subprograms.bucketfill_cru()

@app.command()
def spatial_crop_cru():
    print("Need to call the spatial_crop_cru func...")
    subprograms.spatial_crop_cru()

@app.command()
def prepare_aoi():
    print("Should start from scratch, download some data for the aoi mask, and "
          "create the aoi based on the downloaded files. results in two shape "
          "files in your 'working' directory")

@app.command()
def prepare_tile_folders():
    print("Run this after you have an AOI. This cuts the AOI up into tiles and "
          "makes a folder for each tile. Inside each folder will be some shape "
          "files that define the tile extent. There should also be a tile "
          "index file that is a shape file with a polygon for each tile folder")
    



@app.command()
def setup(
        what: str,
        config: Annotated[str, typer.Argument(help="YAML configuration to use in lieu of command line arguments")]=None, 
        root: str = None, 
        # aoi:str=None, 
        # download:str=None, 
        # preprocessed:str=None, 
        # tiles:str=None, 
        # final:str=None
    ):
    print(root)
    if 'directories' == what:
        subprograms.setup_directories(
            config, #root , aoi, download, preprocessed, tiles, final
        )
    elif 'clean' == what:
        print('should clean up stuff') 

@app.command()
def download(
        what: Annotated[str, typer.Argument(help="Name of the dataset to download")], 
        config: Annotated[str, typer.Argument(help="YAML configuration to use in lieu of command line arguments")]=None, 
        save_to: Annotated[str, typer.Argument(help="Location where downloaded data is saved")]='default', 
        url_pattern: Annotated[str, typer.Argument(help="URL pattern for remote data ")]='default', 
        overwrite: Annotated[bool, typer.Argument(help="Flag to overwrite existing data")]=True, 
    ):

    subprograms.download(what, config, save_to, url_pattern, overwrite)

@app.command()
def preprocess(what: str, where: str = 'default'):
    print(f"Preprocessing {what}")
    ## IF data is missing download first
    ## currently download() does this
    # TODO

# @ app.command() ## want somthing like this but need to look into typer more
# def run(subprograms: List[VALID_SUBPROGRAMS], config: str):
#     if 'download' in list:
#         print('downloading')
#         # download('worldclim', config)


# ============================================================================
# Pipeline Commands
# ============================================================================

@app.command()
def pipeline_run(
    config_file: Annotated[str, typer.Argument(help="Path to pipeline YAML configuration file")],
    aoi: Annotated[Optional[List[str]], typer.Option("--aoi", "-a", help="Specific AOI(s) to process")] = None,
    from_step: Annotated[Optional[str], typer.Option("--from-step", help="Start from this step (inclusive)")] = None,
    to_step: Annotated[Optional[str], typer.Option("--to-step", help="Stop at this step (inclusive)")] = None,
    only_step: Annotated[Optional[str], typer.Option("--only-step", help="Run only this specific step")] = None,
    force_all: Annotated[bool, typer.Option("--force-all", help="Force re-run all steps, ignoring cache")] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose logging")] = False,
):
    """Run the data processing pipeline from a configuration file.
    
    Examples:
        # Run full pipeline for all AOIs
        temds pipeline-run pipeline.yaml
        
        # Run only for specific AOI
        temds pipeline-run pipeline.yaml --aoi temrs_path_0
        
        # Run specific step only
        temds pipeline-run pipeline.yaml --only-step worldclim
        
        # Run from step to end
        temds pipeline-run pipeline.yaml --from-step cru
        
        # Force re-run ignoring cache
        temds pipeline-run pipeline.yaml --force-all
    """
    # Configure logger based on verbose flag
    log_level = temds.logger.DEBUG if verbose else temds.logger.INFO
    logger = temds.logger.Logger([], log_level)
    
    try:
        pipeline = Pipeline.from_config_file(config_file, logger=logger)
        pipeline.run(
            aoi_names=aoi,
            from_step=from_step,
            to_step=to_step,
            only_step=only_step,
            force_all=force_all
        )
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        raise typer.Exit(code=1)


@app.command()
def pipeline_list_steps(
    config_file: Annotated[Optional[str], typer.Argument(help="Path to pipeline YAML configuration file")] = None,
):
    """List available pipeline steps in execution order.
    
    Examples:
        temds pipeline-list-steps
        temds pipeline-list-steps pipeline.yaml  # Show which steps are enabled
    """
    from .pipeline import Pipeline
    
    typer.echo("Available pipeline steps (in execution order):")
    typer.echo()
    
    for i, step in enumerate(Pipeline.STEP_ORDER, 1):
        typer.echo(f"  {i}. {step}")
    
    if config_file:
        from .pipeline.config import PipelineConfig
        config = PipelineConfig.from_yaml(config_file)
        typer.echo("\nStep status in configuration:")
        for step in Pipeline.STEP_ORDER:
            step_config = config.get_step_config(step)
            status = "✓ enabled" if step_config.enabled else "✗ disabled"
            if step_config.force:
                status += " (forced)"
            typer.echo(f"  {step}: {status}")


@app.command()
def pipeline_cache_status(
    config_file: Annotated[str, typer.Argument(help="Path to pipeline YAML configuration file")],
    aoi: Annotated[Optional[str], typer.Option("--aoi", "-a", help="Specific AOI to check")] = None,
):
    """Show cache status for pipeline steps.
    
    Examples:
        temds pipeline-cache-status pipeline.yaml
        temds pipeline-cache-status pipeline.yaml --aoi temrs_path_0
    """
    from .pipeline.config import PipelineConfig
    from .pipeline.cache import CacheManager
    
    config = PipelineConfig.from_yaml(config_file)
    
    # Filter AOIs
    aois = config.aois
    if aoi:
        aois = [a for a in aois if a.name == aoi]
        if not aois:
            typer.echo(f"Error: AOI '{aoi}' not found in configuration", err=True)
            raise typer.Exit(code=1)
    
    # Check cache for each AOI
    for aoi_config in aois:
        cache_manager = CacheManager(
            config.working_dir,
            aoi_config.name,
            config.resolution,
            config.crs
        )
        
        typer.echo(f"\nCache status for AOI: {aoi_config.name}")
        typer.echo("=" * 60)
        
        status = cache_manager.get_all_steps()
        for step, is_valid in status.items():
            if is_valid:
                path = cache_manager.get_path(step)
                typer.echo(f"  ✓ {step:20s} {path}")
            else:
                typer.echo(f"  ✗ {step:20s} (not cached)")


@app.command()
def pipeline_init(
    output_file: Annotated[str, typer.Argument(help="Path for new configuration file")] = "pipeline.yaml",
):
    """Create a sample pipeline configuration file.
    
    Examples:
        temds pipeline-init
        temds pipeline-init my-pipeline.yaml
    """
    from .pipeline.config import PipelineConfig, AOIConfig, DataSourcePaths, TileConfig
    
    # Create sample configuration
    config = PipelineConfig(
        aois=[
            AOIConfig(
                name="example_aoi",
                vector_file="path/to/aoi.geojson"
            )
        ],
        working_dir="working",
        resolution=1000,
        crs="EPSG:6931",
        data_sources=DataSourcePaths(
            worldclim="working/00-download/worldclim",
            vegetation="working/00-download/veg/NA_LandCover_2005_vector.shp",
            topography="working/00-download/topo/aspect_1KMmd_GMTEDmd.tif",
            soil_texture="working/00-download/soil/soil_TAWCmm.tif",
            fri="synthetic",
            cru="working/00-download/cru"
        ),
        tile_config=TileConfig(
            process_tiles=False,
            tile_indices=["H01_V01"],
            baseline_start_year=1901,
            baseline_end_year=1930,
            downscale=True
        ),
        verbose=False
    )
    
    config.to_yaml(output_file)
    typer.echo(f"Created sample configuration: {output_file}")
    typer.echo("\nEdit this file to customize:")
    typer.echo("  - AOI names and vector files")
    typer.echo("  - Data source paths")
    typer.echo("  - Enable/disable steps")
    typer.echo("  - Tile processing options")


if __name__ == "__main__":
    app()
