"""Core pipeline execution engine."""

import time
from pathlib import Path
from typing import Optional, List, Set, Callable, Dict, Any
from functools import wraps

import temds

from ..logger import Logger
from ..aoitools import AOIMask, TileIndex
from ..datasources.dataset import TEMDataset
from ..datasources.timeseries import YearlyTimeSeries
from ..tile import Tile

from .config import PipelineConfig, AOIConfig
from .cache import CacheManager


def pipeline_step(step_name: str):
    """Decorator to register and track pipeline steps.
    
    Args:
        step_name: Name of the step for logging and caching
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self: 'Pipeline', *args, **kwargs):
            # Check if step is enabled
            if not self.config.is_step_enabled(step_name):
                self.logger.info(f"Step '{step_name}' is disabled, skipping")
                return None
            
            step_config = self.config.get_step_config(step_name)
            
            # Check cache unless force is enabled
            if step_config.cache and not step_config.force and not self.force_all:
                cache_manager = kwargs.get('cache_manager')
                if cache_manager and cache_manager.validate(step_name):
                    cache_path = cache_manager.get_path(step_name)
                    self.logger.info(f"✓ Cache hit for '{step_name}': {cache_path}")
                    self.stats['steps_cached'] += 1
                    return cache_path
            
            # Run the step
            self.logger.info(f"Running step '{step_name}'...")
            start_time = time.time()
            
            result = func(self, *args, **kwargs)
            
            elapsed = time.time() - start_time
            self.logger.info(f"✓ Completed '{step_name}' in {elapsed:.1f}s")
            self.stats['steps_run'] += 1
            
            return result
        
        wrapper._step_name = step_name
        wrapper._is_pipeline_step = True
        return wrapper
    
    return decorator


class Pipeline:
    """Repeatable pipeline for processing climate data.
    
    The pipeline processes one or more AOIs through a series of configurable steps,
    with automatic caching and resume capability.
    """
    
    # Step ordering for execution
    STEP_ORDER = [
        "aoi_raster",
        "worldclim",
        "vegetation", 
        "topography",
        "soil_texture",
        "fri",
        "cru",
        "tile_index",
        "tiles"
    ]
    
    def __init__(self, config: PipelineConfig, logger: Optional[Logger] = None):
        """Initialize pipeline.
        
        Args:
            config: Pipeline configuration
            logger: Optional logger instance
        """
        self.config = config
        self.logger = logger or Logger()
        self.force_all = False
        
        # Statistics tracking
        self.stats = {
            'steps_run': 0,
            'steps_cached': 0,
            'steps_skipped': 0,
            'aois_processed': 0
        }
    
    @classmethod
    def from_config_file(cls, config_path: str | Path, logger: Optional[Logger] = None) -> "Pipeline":
        """Create pipeline from YAML configuration file.
        
        Args:
            config_path: Path to YAML configuration file
            logger: Optional logger instance
            
        Returns:
            Pipeline instance
        """
        config = PipelineConfig.from_yaml(config_path)
        return cls(config, logger)
    
    def run(
        self, 
        aoi_names: Optional[List[str]] = None,
        from_step: Optional[str] = None,
        to_step: Optional[str] = None, 
        only_step: Optional[str] = None,
        force_all: bool = False
    ) -> None:
        """Run the pipeline.
        
        Args:
            aoi_names: Specific AOI names to process (None = all)
            from_step: Start from this step (inclusive)
            to_step: Stop at this step (inclusive)
            only_step: Run only this specific step
            force_all: Force re-run of all steps, ignoring cache
        """
        self.force_all = force_all
        start_time = time.time()
        
        # Filter AOIs if specific names provided
        aois = self.config.aois
        if aoi_names:
            aois = [aoi for aoi in aois if aoi.name in aoi_names]
            if not aois:
                self.logger.error(f"No AOIs found matching: {aoi_names}")
                return
        
        self.logger.info(f"Starting pipeline for {len(aois)} AOI(s)")
        
        # Process each AOI
        for aoi in aois:
            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"Processing AOI: {aoi.name}")
            self.logger.info(f"{'='*60}")
            
            self.run_for_aoi(
                aoi, 
                from_step=from_step,
                to_step=to_step,
                only_step=only_step
            )
            
            self.stats['aois_processed'] += 1
        
        # Print summary
        elapsed = time.time() - start_time
        self.logger.info(f"\n{'='*60}")
        self.logger.info("Pipeline Complete!")
        self.logger.info(f"{'='*60}")
        self.logger.info(f"AOIs processed: {self.stats['aois_processed']}")
        self.logger.info(f"Steps run: {self.stats['steps_run']}")
        self.logger.info(f"Steps cached: {self.stats['steps_cached']}")
        self.logger.info(f"Steps skipped: {self.stats['steps_skipped']}")
        self.logger.info(f"Total time: {elapsed:.1f}s")
    
    def run_for_aoi(
        self,
        aoi: AOIConfig,
        from_step: Optional[str] = None,
        to_step: Optional[str] = None,
        only_step: Optional[str] = None
    ) -> None:
        """Run pipeline steps for a single AOI.
        
        Args:
            aoi: AOI configuration
            from_step: Start from this step (inclusive)
            to_step: Stop at this step (inclusive)
            only_step: Run only this specific step
        """
        # Initialize cache manager for this AOI
        cache_manager = CacheManager(
            self.config.working_dir,
            aoi.name,
            self.config.resolution,
            self.config.crs
        )
        
        # Create necessary directories
        cache_manager.aoi_dir.mkdir(parents=True, exist_ok=True)
        cache_manager.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine which steps to run
        steps_to_run = self._get_steps_to_run(from_step, to_step, only_step)
        
        # Run each step in order
        for step_name in steps_to_run:
            if step_name == "aoi_raster":
                self._step_aoi_raster(aoi, cache_manager)
            elif step_name == "worldclim":
                self._step_worldclim(aoi, cache_manager)
            elif step_name == "vegetation":
                self._step_vegetation(aoi, cache_manager)
            elif step_name == "topography":
                self._step_topography(aoi, cache_manager)
            elif step_name == "soil_texture":
                self._step_soil_texture(aoi, cache_manager)
            elif step_name == "fri":
                self._step_fri(aoi, cache_manager)
            elif step_name == "cru":
                self._step_cru(aoi, cache_manager)
            elif step_name == "tile_index":
                self._step_tile_index(aoi, cache_manager)
            elif step_name == "tiles":
                self._step_tiles(aoi, cache_manager)
            else:
                self.logger.warning(f"Unknown step: {step_name}")
    
    def _get_steps_to_run(
        self,
        from_step: Optional[str],
        to_step: Optional[str],
        only_step: Optional[str]
    ) -> List[str]:
        """Determine which steps to run based on filters.
        
        Args:
            from_step: Start from this step
            to_step: Stop at this step
            only_step: Run only this step
            
        Returns:
            List of step names to execute
        """
        if only_step:
            if only_step not in self.STEP_ORDER:
                raise ValueError(f"Unknown step: {only_step}")
            return [only_step]
        
        steps = list(self.STEP_ORDER)
        
        if from_step:
            if from_step not in steps:
                raise ValueError(f"Unknown step: {from_step}")
            from_idx = steps.index(from_step)
            steps = steps[from_idx:]
        
        if to_step:
            if to_step not in steps:
                raise ValueError(f"Unknown step: {to_step}")
            to_idx = steps.index(to_step)
            steps = steps[:to_idx + 1]
        
        return steps
    
    # ========================================================================
    # Pipeline Steps
    # ========================================================================
    
    @pipeline_step("aoi_raster")
    def _step_aoi_raster(self, aoi: AOIConfig, cache_manager: CacheManager) -> Path:
        """Load AOI vector and create rasterized version.
        
        Args:
            aoi: AOI configuration
            cache_manager: Cache manager for this AOI
            
        Returns:
            Path to rasterized AOI file
        """
        # Load vector
        aoi_mask = AOIMask.load_vector(aoi.vector_file)
        
        # Create raster
        output_path = cache_manager.get_path("aoi_raster")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        aoi_mask.to_rasterfile(
            where=str(output_path.parent),
            name=output_path.stem,
            resolution=self.config.resolution,
            crs=self.config.crs
        )
        
        return output_path
    
    @pipeline_step("worldclim")
    def _step_worldclim(self, aoi: AOIConfig, cache_manager: CacheManager) -> Path:
        """Load and cache WorldClim data for AOI extent.
        
        Args:
            aoi: AOI configuration
            cache_manager: Cache manager for this AOI
            
        Returns:
            Path to cached WorldClim data
        """
        aoi_raster = cache_manager.get_path("aoi_raster")
        if not aoi_raster.exists():
            raise FileNotFoundError(f"AOI raster not found: {aoi_raster}. Run aoi_raster step first.")
        
        wc = TEMDataset.from_worldclim(
            data_path=self.config.data_sources.worldclim,
            download=False,
            extent_raster=str(aoi_raster),
            logger=self.logger
        )
        
        output_path = cache_manager.get_path("worldclim")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        wc.save(str(output_path))
        
        return output_path
    
    @pipeline_step("vegetation")
    def _step_vegetation(self, aoi: AOIConfig, cache_manager: CacheManager) -> Path:
        """Load and cache vegetation data for AOI extent.
        
        Args:
            aoi: AOI configuration
            cache_manager: Cache manager for this AOI
            
        Returns:
            Path to cached vegetation data
        """
        aoi_raster = cache_manager.get_path("aoi_raster")
        if not aoi_raster.exists():
            raise FileNotFoundError(f"AOI raster not found: {aoi_raster}. Run aoi_raster step first.")
        
        veg = TEMDataset.from_vegetation(
            data_path=self.config.data_sources.vegetation,
            extent_raster=str(aoi_raster),
            download=False,
            logger=self.logger
        )
        
        output_path = cache_manager.get_path("vegetation")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        veg.save(str(output_path))
        
        return output_path
    
    @pipeline_step("topography")
    def _step_topography(self, aoi: AOIConfig, cache_manager: CacheManager) -> Path:
        """Load and cache topography data for AOI extent.
        
        Args:
            aoi: AOI configuration
            cache_manager: Cache manager for this AOI
            
        Returns:
            Path to cached topography data
        """
        aoi_raster = cache_manager.get_path("aoi_raster")
        if not aoi_raster.exists():
            raise FileNotFoundError(f"AOI raster not found: {aoi_raster}. Run aoi_raster step first.")
        
        topo = TEMDataset.from_topo(
            data_path=self.config.data_sources.topography,
            extent_raster=str(aoi_raster),
            download=False,
            logger=self.logger
        )
        
        output_path = cache_manager.get_path("topography")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        topo.save(str(output_path))
        
        return output_path
    
    @pipeline_step("soil_texture")
    def _step_soil_texture(self, aoi: AOIConfig, cache_manager: CacheManager) -> Path:
        """Load and cache soil texture data for AOI extent.
        
        Args:
            aoi: AOI configuration
            cache_manager: Cache manager for this AOI
            
        Returns:
            Path to cached soil texture data
        """
        aoi_raster = cache_manager.get_path("aoi_raster")
        if not aoi_raster.exists():
            raise FileNotFoundError(f"AOI raster not found: {aoi_raster}. Run aoi_raster step first.")
        
        soil = TEMDataset.from_soil_texture(
            data_path=self.config.data_sources.soil_texture,
            extent_raster=str(aoi_raster),
            download=False,
            logger=self.logger
        )
        
        output_path = cache_manager.get_path("soil_texture")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        soil.save(str(output_path))
        
        return output_path
    
    @pipeline_step("fri")
    def _step_fri(self, aoi: AOIConfig, cache_manager: CacheManager) -> Path:
        """Load and cache FRI fire data for AOI extent.
        
        Args:
            aoi: AOI configuration
            cache_manager: Cache manager for this AOI
            
        Returns:
            Path to cached FRI data
        """
        aoi_raster = cache_manager.get_path("aoi_raster")
        if not aoi_raster.exists():
            raise FileNotFoundError(f"AOI raster not found: {aoi_raster}. Run aoi_raster step first.")
        
        # Check if synthetic or real data
        synthetic = (self.config.data_sources.fri == "synthetic")
        
        fri = TEMDataset.from_fri(
            synthetic=synthetic,
            extent_raster_path=str(aoi_raster) if synthetic else None,
            logger=self.logger
        )
        
        output_path = cache_manager.get_path("fri")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fri.save(str(output_path))
        
        return output_path
    
    @pipeline_step("cru")
    def _step_cru(self, aoi: AOIConfig, cache_manager: CacheManager) -> Path:
        """Load and cache CRU-JRA timeseries data for AOI extent.
        
        Args:
            aoi: AOI configuration
            cache_manager: Cache manager for this AOI
            
        Returns:
            Path to cached CRU data directory
        """
        aoi_raster = cache_manager.get_path("aoi_raster")
        if not aoi_raster.exists():
            raise FileNotFoundError(f"AOI raster not found: {aoi_raster}. Run aoi_raster step first.")
        
        if not self.config.data_sources.cru:
            self.logger.warning("CRU data path not configured, skipping")
            self.stats['steps_skipped'] += 1
            return None
        
        # Load timeseries
        # cru_ts = YearlyTimeSeries(
        #     data=self.config.data_sources.cru,
        #     logger=self.logger
        # )

        cru_arctic = temds.datasources.timeseries.YearlyTimeSeries(
          Path(self.config.data_sources.cru),
          #Path('working/02-arctic/cru-jra-fixed-temds/'),
          logger=self.logger,
          in_memory=False,
        )

        # original implementation - requires that the aoi_raster is an 
        # aoitools.AOIMask with aoi attribute, which is not currently the case.
        # Need to refactor to use raster extent instead.
        # cru_subset = cru_arctic.get_by_extent(
        #     *(aoi_raster().iloc[0].values),
        #     extent_crs=aoi_raster.aoi.crs, 
        #     resolution=self.config.resolution, 
        #     in_memory=True
        # )


        # New implementation - simply read the extent from the aoi raster file 
        # and subset the CRU data to that extent. This should be more flexible 
        # and work with any rasterized AOI, not just those created by aoitools.
        # Get extent from AOI raster
        import rioxarray
        with rioxarray.open_rasterio(aoi_raster) as aoi_ds:
            bounds = aoi_ds.rio.bounds()
            extent_crs = aoi_ds.rio.crs
        
        # Subset to AOI extent
        cru_subset = cru_arctic.get_by_extent(
            minx=bounds[0], miny=bounds[1],
            maxx=bounds[2], maxy=bounds[3],
            extent_crs=extent_crs,
            resolution=self.config.resolution
        )
        
        output_path = cache_manager.get_path("cru")
        output_path.mkdir(parents=True, exist_ok=True)
        cru_subset.save(str(output_path))
        
        return output_path
    
    @pipeline_step("tile_index")
    def _step_tile_index(self, aoi: AOIConfig, cache_manager: CacheManager) -> Path:
        """Create tile index for the AOI.
        
        Args:
            aoi: AOI configuration
            cache_manager: Cache manager for this AOI
            
        Returns:
            Path to tile index file
        """
        aoi_raster = cache_manager.get_path("aoi_raster")
        if not aoi_raster.exists():
            raise FileNotFoundError(f"AOI raster not found: {aoi_raster}. Run aoi_raster step first.")
        
        output_path = cache_manager.get_path("tile_index")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create tile index
        tile_index = create_tile_index(
            extent_raster_path=str(aoi_raster),
            out_file=str(output_path),
            logger=self.logger
        )
        
        return output_path
    
    @pipeline_step("tiles")
    def _step_tiles(self, aoi: AOIConfig, cache_manager: CacheManager) -> None:
        """Process individual tiles.
        
        Args:
            aoi: AOI configuration
            cache_manager: Cache manager for this AOI
        """
        if not self.config.tile_config.process_tiles:
            self.logger.info("Tile processing disabled, skipping")
            self.stats['steps_skipped'] += 1
            return
        
        tile_index_path = cache_manager.get_path("tile_index")
        if not tile_index_path.exists():
            raise FileNotFoundError(f"Tile index not found: {tile_index_path}. Run tile_index step first.")
        
        # Load tile index to get available tiles
        import geopandas as gpd
        tile_index = gpd.read_file(tile_index_path)
        
        # Determine which tiles to process
        if self.config.tile_config.tile_indices:
            tiles_to_process = self.config.tile_config.tile_indices
        elif self.config.tile_config.all_tiles:
            tiles_to_process = tile_index['index'].tolist()
        else:
            self.logger.info("No tiles specified for processing")
            return
        
        self.logger.info(f"Processing {len(tiles_to_process)} tile(s)")
        
        # Process each tile
        for tile_idx in tiles_to_process:
            self._process_single_tile(aoi, cache_manager, tile_idx, tile_index)
    
    def _process_single_tile(
        self,
        aoi: AOIConfig,
        cache_manager: CacheManager,
        tile_idx: str,
        tile_index_gdf
    ) -> None:
        """Process a single tile.
        
        Args:
            aoi: AOI configuration
            cache_manager: Cache manager for this AOI
            tile_idx: Tile index (e.g., 'H01_V02')
            tile_index_gdf: GeoDataFrame containing tile index
        """
        self.logger.info(f"  Processing tile {tile_idx}")
        
        # Check if tile already processed (has valid manifest)
        step_config = self.config.get_step_config("tiles")
        if step_config.cache and not step_config.force and not self.force_all:
            if cache_manager.validate("tile", tile_index=tile_idx):
                self.logger.info(f"  ✓ Tile {tile_idx} already processed (cache hit)")
                return
        
        # Get tile extent from index
        tile_row = tile_index_gdf[tile_index_gdf['index'] == tile_idx]
        if tile_row.empty:
            self.logger.warning(f"  Tile {tile_idx} not found in index")
            return
        
        extent = tile_row.iloc[0].geometry.bounds  # (minx, miny, maxx, maxy)
        
        # Create tile object
        tile = Tile(
            index=tile_idx,
            extent=extent,
            resolution=self.config.resolution,
            crs=self.config.crs,
            logger=self.logger
        )
        
        # Import datasets into tile
        self._import_datasets_to_tile(tile, cache_manager)
        
        # Perform baseline correction and downscaling if requested
        if self.config.tile_config.downscale:
            self._downscale_tile(tile, cache_manager)
        
        # Save tile
        tile_output_dir = cache_manager.get_path("tile", tile_index=tile_idx).parent
        tile_output_dir.mkdir(parents=True, exist_ok=True)
        tile.save(str(tile_output_dir))
        
        self.logger.info(f"  ✓ Tile {tile_idx} complete")
    
    def _import_datasets_to_tile(self, tile: Tile, cache_manager: CacheManager) -> None:
        """Import all datasets into a tile.
        
        Args:
            tile: Tile object
            cache_manager: Cache manager for this AOI
        """
        datasets = {
            "worldclim": "worldclim",
            "veg": "vegetation",
            "topo": "topography",
            "soiltex": "soil_texture",
            "fri-fire": "fri"
        }
        
        for tile_name, step_name in datasets.items():
            dataset_path = cache_manager.get_path(step_name)
            if dataset_path.exists():
                self.logger.info(f"    Importing {tile_name}")
                tile.import_and_normalize(tile_name, str(dataset_path), buffered=True)
            else:
                self.logger.warning(f"    Skipping {tile_name} (not found)")
        
        # Import CRU timeseries
        cru_path = cache_manager.get_path("cru")
        if cru_path.exists() and cru_path.is_dir():
            self.logger.info(f"    Importing CRU timeseries")
            tile.import_and_normalize("cru", str(cru_path), buffered=True)
    
    def _downscale_tile(self, tile: Tile, cache_manager: CacheManager) -> None:
        """Perform baseline correction and downscaling on a tile.
        
        Args:
            tile: Tile object
            cache_manager: Cache manager for this AOI
        """
        # Calculate baseline
        self.logger.info(f"    Calculating baseline")
        tile.calculate_climate_baseline(
            start_year=self.config.tile_config.baseline_start_year,
            end_year=self.config.tile_config.baseline_end_year,
            target='cru-baseline',
            source='cru'
        )
        
        # Calculate correction factors
        self.logger.info(f"    Calculating correction factors")
        tile.calculate_correction_factors(
            baseline_id='cru-baseline',
            reference_id='worldclim',
            variables=['tair', 'prec'],
            factor_id='cru-correction'
        )
        
        # Downscale timeseries
        self.logger.info(f"    Downscaling timeseries")
        tile.downscale_timeseries(
            downscaled_id='cru-downscaled',
            source_id='cru',
            correction_id='cru-correction',
            variables=['tair', 'prec'],
            parallel=False
        )
