"""Core pipeline execution engine."""

import time
from pathlib import Path
from typing import Optional, List, Set, Callable, Dict, Any
from functools import wraps
import numpy as np

import temds

from ..logger import Logger
from ..aoitools import TileIndex
from ..datasources.dataset import TEMDataset
from ..datasources.timeseries import YearlyTimeSeries
from ..tile import Tile

from .config import PipelineConfig, AOIConfig
from .cache import CacheManager
from temds import tile

def get_aoi_info(cache_manager: CacheManager, logger: Optional[Logger] = None)-> tuple[float, float, float, float, str]:
    '''This needs a better name or maybe should be part of the aoi class??
    But at least here it is reusable across steps, so 'till we think of a 
    something better....'''

    # Read the extent from the aoi raster file 
    import rioxarray as rxr
    with rxr.open_rasterio(cache_manager.get_path("aoi_raster")) as aoi_ds:
        #bounds = aoi_ds.rio.bounds()
        extent_crs = aoi_ds.rio.crs

    if logger:
        logger.debug(f'Pipeline.get_aoi_info(): Using extent from {cache_manager.get_path("aoi_raster")}')


    # Steal this part from the soil data set creation...
    from osgeo import gdal
    er = gdal.Open(cache_manager.get_path("aoi_raster"))
    # Get the extent from the extent raster
    er_gt = er.GetGeoTransform()
    er_minx = er_gt[0]
    er_miny = er_gt[3]
    er_maxx = er_gt[0] + (er_gt[1] * er.RasterXSize)
    er_maxy = er_gt[3] + (er_gt[5] * er.RasterYSize)

    return er_minx, er_maxx, er_miny, er_maxy, extent_crs



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
                # Extract cache_manager from args (second positional argument)
                cache_manager = args[1] if len(args) > 1 else kwargs.get('cache_manager')
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
        "cmip6",
        "setup_tiles",
        "process_tiles", # includes import, baseline, correction and downscaling...
        "export_tiles",  # includes resampling to TEM resolution...

        # # --- Tile-based steps below ---
        # "tile_import",      # Import AOI-level data into each tile
        # "tile_baseline",    # Calculate baseline per tile
        # "tile_correction",  # Calculate correction factors per tile
        # "tile_downscale",   # Downscale timeseries per tile
    ]
    
    def __init__(self, config: PipelineConfig, logger: Optional[Logger] = None):
        """Initialize pipeline.
        
        Args:
            config: Pipeline configuration
            logger: Optional logger instance
        """
        self.config = config
        self.logger = logger if logger is not None else Logger()
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
            #self.logger.info(f"\n{'='*60}")
            self.logger.info(f"Processing AOI: {aoi.name}")
            #self.logger.info(f"{'='*60}")
            
            self.run_for_aoi(
                aoi, 
                from_step=from_step,
                to_step=to_step,
                only_step=only_step
            )
            
            self.stats['aois_processed'] += 1
        
        # Print summary
        elapsed = time.time() - start_time
        #self.logger.info(f"\n{'='*60}")
        self.logger.info("Pipeline Complete!")
        #self.logger.info(f"{'='*60}")
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
            elif step_name == "cmip6":
                self._step_cmip6(aoi, cache_manager)
            elif step_name == "setup_tiles":
                self._step_setup_tiles(aoi, cache_manager)
            elif step_name == "process_tiles":
                self._step_process_tiles(aoi, cache_manager)
            elif step_name == "export_tiles":
                self._step_export_tiles(aoi, cache_manager)
            else:
                self.logger.warn(f"Unknown step: {step_name}")
    
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

        from osgeo import gdal 
        import geopandas as gpd
        import temds.region.tools
 
        raw_aoi = gpd.read_file(aoi.vector_file)
        assert raw_aoi.crs == 3338

        converted_aoi = raw_aoi.to_crs(6931)
        assert converted_aoi.crs == 6931

        # TODO: fix the hard coded resolution....
        assert self.config.resolution == 1000, "Currently resolution is hard coded to 1000m in this step, but it should be unified across the codebase. Please update the config or the code to match."


        # Here we get a dataframe with two rows. One row has the geometry for
        # the original mask, and the other row has a geometry for the bounds of
        # the mask, but aligned to the resolution. This is because
        # gdal.Rasterize needs the bounds to be aligned to the resolution, but
        # we also want to keep the original shape of the mask for burning into
        # the raster
        better_aoi = temds.region.tools.align_to_resolution(converted_aoi, 1000)

        bounds = better_aoi[better_aoi['item']=='res_aligned_bounds'].geometry.bounds.iloc[0]

        ds, layer = temds.region.tools.geopandas_to_ogr_dataset(better_aoi.loc[[0], "geometry"], layer_name='run_mask')
        opts = gdal.RasterizeOptions(
          format='GTIFF',
          outputBounds=(bounds['minx'], bounds['miny'], bounds['maxx'], bounds['maxy']),
          outputSRS='EPSG:6931',  # Added: specify output CRS
          xRes=1000,
          yRes=1000,
          noData=0,
          burnValues=[1],
          allTouched=True,
          initValues=0,
          layers=[layer.GetName()],
          outputType=gdal.GDT_Int16
        )

        rds = gdal.Rasterize(cache_manager.get_path("aoi_raster"), ds, options=opts)
        
        # Flush and close the dataset to ensure it's written to disk
        rds.FlushCache()
        rds = None

        # # Create raster
        output_path = cache_manager.get_path("aoi_raster")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
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
        wc.save(str(output_path), overwrite=True)
        
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
        veg.save(str(output_path), overwrite=True, fill_value=np.int32(-9999), missing_value=np.int32(-9999))
        
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
        topo.save(str(output_path), overwrite=True, fill_value=np.int32(-9999), missing_value=np.int32(-9999))
        
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
        soil.save(str(output_path), overwrite=True, fill_value=np.int32(-9999), missing_value=np.int32(-9999))
        
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
        fri.save(str(output_path), overwrite=True, fill_value=np.int32(-9999), missing_value=np.int32(-9999))
        
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
        
        self.logger.debug(f"Loading CRU data from: {self.config.data_sources.cru}")
        cru_arctic = temds.datasources.timeseries.YearlyTimeSeries(
          Path(self.config.data_sources.cru),
          logger=self.logger,
          in_memory=False,
        )

        minx, maxx, miny, maxy, extent_crs = get_aoi_info()
        cru_subset = cru_arctic.get_by_extent(
            minx=minx, maxx=maxx, miny=miny, maxy=maxy,
            extent_crs = extent_crs,
            resolution=self.config.resolution,
            in_memory=True)
 
        
        output_path = cache_manager.get_path("cru")
        output_path.mkdir(parents=True, exist_ok=True)
        cru_subset.save(
            output_path,
            #cache_manager.get_path("cru"),
            #f"{cache_manager.data_dir}/{AOI_NAME}_cru}/",
            name_pattern=f'{aoi.name}_cru_{{year}}.nc',
            overwrite=True, complevel=1
        )


        return output_path
    
    @pipeline_step("cmip6")
    def _step_cmip6(self, aoi: AOIConfig, cache_manager: CacheManager) -> Path:
        """Load and cache CMIP6 timeseries data for AOI extent."""

        import temds.datasources

        aoi_raster = cache_manager.get_path("aoi_raster")
        if not aoi_raster.exists():
            raise FileNotFoundError(f"AOI raster not found: {aoi_raster}. Run aoi_raster step first.")

        source_id = 'cmip6'
        time_frequency = 'day'

        cmiphist = []
        ssp245 = []

        for year in range(1950, 2015):
            self.logger.info(f"Loading CMIP6 historical data for year {year}...")
            cmiphist.append(
                temds.datasources.timeseries.YearlyDataset.from_cmip6(
                    year, 
                    'working/00-download/cmip6/', 
                    experimentid='historical', # <- must match name in downloaded files.
                    logger=self.logger
                )
            )
        cmiphist = temds.datasources.timeseries.YearlyTimeSeries(cmiphist, logger=self.logger)
        from IPython import embed; embed()

        cmiphist.save('working/00-download/cmip6-preprocess/cmip6-CESM2-hist/', 'hist-{year}.nc', overwrite=True, complevel=1)


        for year in range(2015, 2040):
            self.logger.info(f"Loading CMIP6 SSP245 data for year {year}...")
            ssp245.append(
                temds.datasources.timeseries.YearlyDataset.from_cmip6(
                    year, 
                    'working/00-download/cmip6/', 
                    experimentid='ssp245', 
                    logger=self.logger
                )
            )

        self.logger.info("CMIP6 YearlyDatasets loaded, creating YearlyTimeSeries objects...")
        ssp245 = temds.datasources.timeseries.YearlyTimeSeries(ssp245, logger=self.logger)
        ssp245.save('working/00-download/cmip6-preprocess/cmip6-CESM2-ssp245/', 'ssp245-{year}.nc', overwrite=True, complevel=0)



        cru = temds.datasources.timeseries.YearlyTimeSeries(Path("working/02-arctic/cru-jra-fixed-temds/"))


        # And  load saved data here...
        ssp245 = temds.datasources.timeseries.YearlyTimeSeries(Path('working/00-download/cmip6-preprocess/cmip6-CESM2-ssp245/'), logger=self.logger)
        cmiphist = temds.datasources.timeseries.YearlyTimeSeries(Path('working/00-download/cmip6-preprocess/cmip6-CESM2-hist/'), logger=self.logger)




        cru = temds.datasources.timeseries.YearlyTimeSeries(Path("working/02-arctic/cru-jra-fixed-temds/"))

        import geopandas as gpd
        boundary = gpd.read_file(aoi.vector_file)

        #topo = cache_manager.get_path("topography")

        # Open the boundary file (geojson)
        # get the bounds of the raster for the aoi
        # load the topo and worldclim from the cache
        # make a tile with the following dataset 
        # - cru 
        # - cmip6



        ###############
        #     
        # Get tile index from setup_tiles output
        tile_dir = cache_manager.get_path("setup_tiles")
        tile_index_path = tile_dir / "tile_index.geojson"
        if not tile_index_path.exists():
            raise FileNotFoundError(f"Tile index not found: {tile_index_path}. Run setup_tiles step first.")
        
        # Load tile index to get available tiles
        import geopandas as gpd
        tile_index = gpd.read_file(tile_index_path)
        
        # Determine which tiles to process
        if self.config.tile_config.tile_indices:
            tiles_to_process = self.config.tile_config.tile_indices
        elif self.config.tile_config.all_tiles:
            # Use 'tile_id' column which has format like 'H01_V02'
            tiles_to_process = tile_index['tile_id'].tolist()
        else:
            self.logger.info("No tiles specified for processing")
            return
        
        self.logger.info(f"Processing {len(tiles_to_process)} tile(s)")
        
        # Process each tile
        for tile_idx in tiles_to_process:

            self.logger.info(f"  Processing tile {tile_idx}")

            # Check if tile already processed (has valid manifest)
            step_config = self.config.get_step_config("tiles")
            if step_config.cache and not step_config.force and not self.force_all:
                pass # TODO, check if tile has manifest has cmip6 and cru data, and if so skip processing
            
            # Tile not in cache, (or cache invalid), so we need to process it

            # Get tile extent from index
            tile_row = tile_index[tile_index['tile_id'] == tile_idx]
            if tile_row.empty:
                self.logger.warn(f"  Tile {tile_idx} not found in index")
                return
            
            extent = tile_row.iloc[0].geometry.bounds  # (minx, miny, maxx, maxy)
            self.logger.info(f"  Tile {tile_idx} extent: {extent}")

            def convert(x):
                # Convert 'H01_V02' to (1, 2)
                parts = x.split('_')
                h = int(parts[0][1:])  # Remove 'H' and convert to int
                v = int(parts[1][1:])  # Remove 'V' and convert to int
                return (h, v)
    



            # Create tile object
            tile = Tile(
                index=convert(tile_idx),
                extent=extent,
                resolution=self.config.resolution,
                crs=self.config.crs,
                buffer_px=0,
                logger=self.logger
            )
            tile.load_from_directory(cache_manager.get_path("process_tiles", tile_index=tile_idx) / tile_idx)
        
        
            tile.import_and_normalize('ssp245', ssp245, False, 
                                    callback=temds.datasources.cmip6.callback_psl_to_vapo, 
                                    elevation=tile.data['topography'].dataset.elevation)

            tile.import_and_normalize('cmiphist', cmiphist, False,
                                    callback=temds.datasources.cmip6.callback_psl_to_vapo,
                                    elevation=tile.data['topography'].dataset.elevation)

            tile.save('working/03-temrs_site7/tiles/', items=['ssp245'])
            tile.save('working/03-temrs_site7/tiles/', items=['cmiphist'])

            tile.calculate_climate_baseline(1970, 2000, 'cmip-baseline', 'cmiphist') 
            corr_params = {
            # 'tair_max': {'function': 'temperature', 'reference': 'tair_max','baseline':'tair_max', 'name': 'tair_max'},
            # 'tair_min': {'function': 'temperature', 'reference': 'tair_min','baseline':'tair_min', 'name': 'tair_min'},
            'tair_avg': {'function': 'temperature'},# 'reference': 'tair_avg','baseline':'tair_mp', 'name': 'tair_avg'},
            'prec': {'function': 'precipitation'},# 'reference': 'prec','baseline':'pre', 'name': 'prec'},
            'vapo': {'function': 'vapor-pressure'},#  'reference': 'vapo','baseline':'vapo', 'name': 'vapo'},
            'nirr': {'function': 'radiation'},#  'reference': 'nirr','baseline':'nirr', 'name': 'nirr'},
            }
            tile.calculate_climate_baseline(1970, 2000, 'cru-downscaled-ref', 'cru-downscaled')

            ds_params = {
            'tair_avg': {'function': 'temperature'},
            'prec':     {'function': 'precipitation'},
            'vapo':     {'function': 'vapor-pressure'},
            'nirr':     {'function':'radiation'},
            }
            tile.calculate_correction_factors('cmip-baseline', 'cru-downscaled-ref', corr_params, factor_id='correction-factors-cmip')


    @pipeline_step("setup_tiles")
    def _step_setup_tiles(self, aoi: AOIConfig, cache_manager: CacheManager) -> Path:
        """Chops the AOI into tiles and makes a directory for each tile, with a
        rasterized version of the AOI in each tile directory. Then creates a 
        tile index shapefile with the tile extents and IDs.
        
        Args:
            aoi: AOI configuration
            cache_manager: Cache manager for this AOI
        Returns:
            Path to tile index file
        """
        aoi_raster = cache_manager.get_path("aoi_raster")
        if not aoi_raster.exists():
            raise FileNotFoundError(f"AOI raster not found: {aoi_raster}. Run aoi_raster step first.")

        # Create TileIndex object
        tile_root = str(cache_manager.tile_dir)
        tile_index = TileIndex(root=tile_root, aoi_raster=aoi_raster, logger=self.logger)

        # Calculate tile extents and grid size
        tile_index.calculate_tile_extents()
        tile_index.calculate_tile_gridsize()

        # Cut the tileset (creates tile rasters in subdirectories)
        tile_index.cut_tileset(tile_index.calculate_tile_extents(), nickname='')

        # Create the tile index shapefile
        tile_index.create_tile_index(nickname='', id='')

        # Return path to tile index file for caching
        tile_index_path = Path(tile_root) / "tile_index.geojson"
        return tile_index_path
    
    @pipeline_step("export_tiles")
    def _step_export_tiles(self, aoi: AOIConfig, cache_manager: CacheManager) -> None:
        """Export tiles for the AOI.
        
        Args:
            aoi: AOI configuration
            cache_manager: Cache manager for this AOI
        """
        if not self.config.tile_config.export_tiles:
            self.logger.info("Tile export disabled, skipping")
            self.stats['steps_skipped'] += 1
            return

        # Get the tile index from the setup_tiles step
        tile_dir = cache_manager.get_path("setup_tiles")
        tile_index_path = tile_dir / "tile_index.geojson"
        if not tile_index_path.exists():
            raise FileNotFoundError(f"Tile index not found: {tile_index_path}. Run setup_tiles step first.")
    
        # Load tile index to get available tiles
        import geopandas as gpd
        tile_index = gpd.read_file(tile_index_path)

        # Determine which tiles to process
        if self.config.tile_config.tile_indices:
            tiles_to_process = self.config.tile_config.tile_indices
        elif self.config.tile_config.all_tiles:
            # Use 'tile_id' column which has format like 'H01_V02'
            tiles_to_process = tile_index['tile_id'].tolist()
        else:
            self.logger.info("No tiles specified for processing")
            return
        
        self.logger.info(f"Processing {len(tiles_to_process)} tile(s)")
        
        # Process each tile
        for tile_idx in tiles_to_process:
            self._export_single_tile(aoi, cache_manager, tile_idx, tile_index)

    @pipeline_step("process_tiles")
    def _step_process_tiles(self, aoi: AOIConfig, cache_manager: CacheManager) -> None:
        """Check config to see if tile processing is enabled. If so, 
        open the tile index and then loop over the tiles in it, processing each
        if it is specified in the config.
        
        Args:
            aoi: AOI configuration
            cache_manager: Cache manager for this AOI
        """
        if not self.config.tile_config.process_tiles:
            self.logger.info("Tile processing disabled, skipping")
            self.stats['steps_skipped'] += 1
            return
        
        # Get tile index from setup_tiles output
        tile_dir = cache_manager.get_path("setup_tiles")
        tile_index_path = tile_dir / "tile_index.geojson"
        if not tile_index_path.exists():
            raise FileNotFoundError(f"Tile index not found: {tile_index_path}. Run setup_tiles step first.")
        
        # Load tile index to get available tiles
        import geopandas as gpd
        tile_index = gpd.read_file(tile_index_path)
        
        # Determine which tiles to process
        if self.config.tile_config.tile_indices:
            tiles_to_process = self.config.tile_config.tile_indices
        elif self.config.tile_config.all_tiles:
            # Use 'tile_id' column which has format like 'H01_V02'
            tiles_to_process = tile_index['tile_id'].tolist()
        else:
            self.logger.info("No tiles specified for processing")
            return
        
        self.logger.info(f"Processing {len(tiles_to_process)} tile(s)")
        
        # Process each tile
        for tile_idx in tiles_to_process:
            self._process_single_tile(cache_manager, tile_idx, tile_index)
    
    def _process_single_tile(
        self,
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

            # TODO: fix this once we have a better sense of how to validate 
            # tile cache...for now we pass here if we pass --force-all
            if cache_manager.validate("process_tiles", tile_index=tile_idx):
                self.logger.info(f"  ✓ Tile {tile_idx} already processed (cache hit)")
                return
        
        # Tile not in cache, (or cache invalid), so we need to process it

        # Get tile extent from index
        tile_row = tile_index_gdf[tile_index_gdf['tile_id'] == tile_idx]
        if tile_row.empty:
            self.logger.warn(f"  Tile {tile_idx} not found in index")
            return
        
        extent = tile_row.iloc[0].geometry.bounds  # (minx, miny, maxx, maxy)
        self.logger.info(f"  Tile {tile_idx} extent: {extent}")

        def convert(x):
            # Convert 'H01_V02' to (1, 2)
            parts = x.split('_')
            h = int(parts[0][1:])  # Remove 'H' and convert to int
            v = int(parts[1][1:])  # Remove 'V' and convert to int
            return (h, v)
        
        # Create tile object
        tile = Tile(
            index=convert(tile_idx),
            extent=extent,
            resolution=self.config.resolution,
            crs=self.config.crs,
            buffer_px=0,
            logger=self.logger
        )

        print("Pipeline:_process_single_tile(..), right before import and normalize")
        requirements = {
            "worldclim": temds.datasources.dataset.TEMDataset(cache_manager.get_path("worldclim")),
            "vegetation": temds.datasources.dataset.TEMDataset(cache_manager.get_path("vegetation")),
            "topography": temds.datasources.dataset.TEMDataset(cache_manager.get_path("topography")),
            "soil_texture": temds.datasources.dataset.TEMDataset(cache_manager.get_path("soil_texture")),
            "fri": temds.datasources.dataset.TEMDataset(cache_manager.get_path("fri")),
            "cru": temds.datasources.timeseries.YearlyTimeSeries(cache_manager.get_path("cru"))
        }
        for req_k, req_v in requirements.items():
            tile.import_and_normalize(req_k, datasource=req_v)  


        # at this point there are several options:
        # 1. tile directory exists with manifest and data -> validate manifest and load data
        # 2. tile directory exists but manifest is missing or invalid -> re-process and overwrite
        # 3. tile directory does not exist -> process and create
        # 4. tile directoy exists and some data is present, but not all data is 
        #     present (i.e. baseline exists, correction and downscaled missing)
        #     -> re-process and overwrite, but log what was missing

        if self.config.tile_config.downscale:
            self._downscale_tile(tile, cache_manager)
        
        # Save tile
        #tile_output_dir = cache_manager.get_path("process_tiles", tile_index=tile_idx).parent
        tile_output_dir = cache_manager.get_path("process_tiles", tile_index=tile_idx)
        tile_output_dir.mkdir(parents=True, exist_ok=True)
        tile.save(str(tile_output_dir), overwrite=True)
        
        self.logger.info(f"  ✓ Tile {tile_idx} complete")

    def _export_single_tile(self,
            aoi: AOIConfig,
            cache_manager: CacheManager,
            tile_idx: str,
            tile_index_gdf
    ) -> None:
        """Export a tile to a specific format (e.g. TEM, ELM, etc.) for use in modeling."""
        

        self.logger.info(f"  Exporting {tile_idx}")
        # three possibilities:
        # 1. tile is in cache with valid manifest -> skip
        # 2. tile is in cache but manifest is invalid -> re-process
        # 3. tile is not in cache at all -> process
        # Check if tile already processed (has valid manifest)
        step_config = self.config.get_step_config("tiles")
        if step_config.cache and not step_config.force and not self.force_all:

            # TODO: fix this once we have a better sense of how to validate 
            # tile cache...for now we pass here if we pass --force-all
            if cache_manager.validate("export_tiles", tile_index=tile_idx):
                self.logger.info(f"  ✓ Tile {tile_idx} already exported (cache hit)")
                return
        
        # Tile not in cache, (or cache invalid), so we need to process it

        # Get tile extent from index
        tile_row = tile_index_gdf[tile_index_gdf['tile_id'] == tile_idx]
        if tile_row.empty:
            self.logger.warn(f"  Tile {tile_idx} not found in index")
            return
        
        extent = tile_row.iloc[0].geometry.bounds  # (minx, miny, maxx, maxy)
        self.logger.info(f"  Tile {tile_idx} extent: {extent}")

        def convert(x):
            # Convert 'H01_V02' to (1, 2)
            parts = x.split('_')
            h = int(parts[0][1:])  # Remove 'H' and convert to int
            v = int(parts[1][1:])  # Remove 'V' and convert to int
            return (h, v)
        
        # Need to load existing data from the tile directory and then export it...
        # Create tile object
        tile = Tile(
            index=convert(tile_idx),
            extent=extent,
            resolution=self.config.resolution,
            crs=self.config.crs,
            buffer_px=0,
            logger=self.logger
        )

        # THis can take a bit of time...would be nice to be able to 
        # do it in memory...but that might be tricky with the way the pipeline
        # is currently structured...we might need to refactor the pipeline to 
        # be more memory oriented rather than file oriented if we want to avoid
        # all this reading and writing to disk...
        tile.load_from_directory(cache_manager.get_path("process_tiles", tile_index=tile_idx))

        # SMALL PROBLEM HERE: need to figure out a way to make the names more
        # standardized or more flexible...right now the tile needs to have
        # data loaded with exactly the right "downscaled_id" (the name of the
        # dataset in the tile....)

        self.logger.debug(f"Creating export directory for tile {tile_idx}...")
        cache_manager.get_path("export_tiles", tile_index=tile_idx).mkdir(parents=True, exist_ok=True)

        self.logger.debug(f"Exporting co2 for tile {tile_idx} to TEM format...")
        co2 = tile.to_TEM('co2')
        co2.to_netcdf(cache_manager.get_path("export_tiles", tile_index=tile_idx) / "co2.nc", mode='w')

        self.logger.debug(f"Exporting topography for tile {tile_idx} to TEM format...")
        T = tile.to_TEM('topography')
        T['topo_data'].to_netcdf(cache_manager.get_path("export_tiles", tile_index=tile_idx) / "topo.nc", mode='w')
        T['drainage_data'].to_netcdf(cache_manager.get_path("export_tiles", tile_index=tile_idx) / "drainage.nc", mode='w')

        self.logger.debug(f"Exporting vegetation for tile {tile_idx} to TEM format...")
        V = tile.to_TEM('vegetation')
        V.to_netcdf(cache_manager.get_path("export_tiles", tile_index=tile_idx) / "vegetation.nc", mode='w')

        self.logger.debug(f"Exporting soil texture for tile {tile_idx} to TEM format...")
        S = tile.to_TEM('soil_texture')
        S.to_netcdf(cache_manager.get_path("export_tiles", tile_index=tile_idx) / "soil-texture.nc", mode='w')

        self.logger.debug(f"Exporting climate for tile {tile_idx} to TEM format...")
        H = tile.to_TEM('cru-downscaled')
        H.dataset['Y'] = np.arange(H.dataset.sizes['y'])
        H.dataset['X'] = np.arange(H.dataset.sizes['x'])  
        H.save(cache_manager.get_path("export_tiles", tile_index=tile_idx) / "historic-climate.nc", overwrite=True)

        F = tile.to_TEM('fri')
        F.to_netcdf(cache_manager.get_path("export_tiles", tile_index=tile_idx) / "fri-fire.nc", mode='w')

        # OK, this is ridiculous, but here it is. We are just synthesizing
        # this data so we haven't filled out the eariler parts of the process
        # and it is therefore not included in the process tile step.
        # So here we make it, basing the time axis off the historic climate time
        hef = temds.datasources.dataset.TEMDataset.from_historic_explicit_fire(
            synthetic=H.dataset['time'],
            extent_raster_path=cache_manager.get_path("aoi_raster"),
            logger=self.logger,
        )
        # We don't really need to save this - if we are saving it, then it 
        # should probably go in the 02 folder, but it seems strange to put it
        # there in this step (04, export). So this is here for debugging purposes.
        # hef.save(cache_manager.get_path("historic_explicit_fire"),
        #         overwrite=True, fill_value=np.int32(-9999), missing_value=np.int32(-9999))

        # Add the dataset to the tile, then run it thru the export and save it.
        tile.import_and_normalize('historic-ef', datasource=hef)
        HEF = tile.to_TEM('historic-ef')
        HEF.to_netcdf(cache_manager.get_path("export_tiles", tile_index=tile_idx) / "historic-explicit-fire.nc", mode='w')
 

        # import pandas as pd
        # P = H.dataset.copy()
        # P['time'] = H.dataset['time'] + pd.Timedelta(days=365)*(H.dataset['time'].size/12)
        # P.to_netcdf(Path(DIR, 'projected-climate.nc'))

        # PEF = HEF.copy()
        # PEF['time'] = HEF['time'] + pd.Timedelta(days=365)*(HEF['time'].size/12)
        # PEF.to_netcdf(Path(DIR, 'projected-explicit-fire.nc'))    





        
    def _downscale_tile(self, tile: Tile, cache_manager: CacheManager) -> None:
        """Perform baseline correction and downscaling on a tile.
        
        Args:
            tile: Tile object
            cache_manager: Cache manager for this AOI
        """

        # This one needs to check the cache
        #  - if in the cache, proceed
        #  - if not in the cache, then try to load it (import and normalize)
        #  - or try to calculate it if the source data is available (in the cache)
        
        # Calculate baseline
        self.logger.info(f"    Calculating baseline")
        tile.calculate_climate_baseline(
            start_year=self.config.tile_config.baseline_start_year,
            end_year=self.config.tile_config.baseline_end_year,
            target='cru-baseline',
            source='cru'
        )
        
        # Calculate correction factors
        self.logger.info("    Calculating correction factors")
        tile.calculate_correction_factors(
            'cru-baseline',
            'worldclim', 
            temds.climate_variables.DOWNSCALE_SAFE, 
            'cru-delta-cf'
        )

        self.logger.info("    Downscaling timeseries")
        variables_ds = ['tair_avg', 'tair_max', 'tair_min', 'prec', 'nirr', 'wind', 'vapo', 'winddir']
        tile.downscale_timeseries(
            downscaled_id='cru-downscaled', 
            source_id='cru', 
            correction_id='cru-delta-cf', 
            variables=variables_ds, 
            parallel=False
        )
