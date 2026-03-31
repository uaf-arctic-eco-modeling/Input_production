
"""
CLI for running data processing pipelines. 
-------------------

This includes commands to run the full pipeline, list steps, check cache status,
and initialize configuration files.
"""
import typer

from typing import List, Optional

from typing_extensions import Annotated

from temds.pipeline import Pipeline, PipelineConfig, CacheManager
from temds.pipeline.config import AOIConfig, DataSourcePaths, TileConfig
import temds.logger

HELP = """Tools to run processing pipelines and cache results."""

app = typer.Typer(help=HELP, no_args_is_help=True)

NAME = 'pipeline'


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
def list_steps(
    config_file: Annotated[Optional[str], typer.Argument(help="Path to pipeline YAML configuration file")] = None,
):
    """List available pipeline steps in execution order.
    
    Examples:
        temds pipeline list-steps
        temds pipeline list-steps pipeline.yaml  # Show which steps are enabled
    """
    
    typer.echo("Available pipeline steps (in execution order):")
    typer.echo()
    
    for i, step in enumerate(temds.pipeline.Pipeline.STEP_ORDER, 1):
        typer.echo(f"  {i}. {step}")
    
    if config_file:
        config = PipelineConfig.from_yaml(config_file)
        typer.echo("\nStep status in configuration:")
        for step in Pipeline.STEP_ORDER:
            step_config = config.get_step_config(step)
            status = "✓ enabled" if step_config.enabled else "✗ disabled"
            if step_config.force:
                status += " (forced)"
            typer.echo(f"  {step}: {status}")


@app.command()
def cache_status(
    config_file: Annotated[str, typer.Argument(help="Path to pipeline YAML configuration file")],
    aoi: Annotated[Optional[str], typer.Option("--aoi", "-a", help="Specific AOI to check")] = None,
):
    """Show cache status for pipeline steps.
    
    Examples:
        temds pipeline cache-status pipeline.yaml
        temds pipeline cache-status pipeline.yaml --aoi temrs_path_0
    """
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
def init(
    output_file: Annotated[str, typer.Argument(help="Path for new configuration file")] = "pipeline.yaml",
):
    """Create a sample pipeline configuration file.
    
    Examples:
        temds pipeline init
        temds pipeline init my-pipeline.yaml
    """
    
    
    # TODO: I think some of the default values in here are not ideal...
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
