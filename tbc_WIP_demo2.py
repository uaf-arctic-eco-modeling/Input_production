#!/usr/bin/env python3

%load_ext autoreload
%autoreload 2

from pathlib import Path

import numpy as np

import temds.logger
import temds.aoitools
import temds.tile
import temds.datasources.dataset
import temds.datasources.timeseries

# import faulthandler

# faulthandler.enable()

log = temds.logger.Logger([], temds.logger.DEBUG)

# With QGIS, make a new vector layer, put it in edit mode, draw a polygon and
# save. Then can load that polygon here. Then to get raster version, used this:
#
#    anc_aoi.to_rasterfile("working/01-aoi", name='comic-whipsnake')
#    Raster AOI saved to working/01-aoi/comic-whipsnake/comic-whipsnake_6931_4000m.tiff
#
# Then you can load either variant

def exercise_AOI( AOI_NAME, wc=True, veg=True, cru=False, topo=True, tile=False ):

  aoi = temds.aoitools.AOIMask.load_vector(f"working/01-aoi/{AOI_NAME}/{AOI_NAME}.shp")
  aoi.to_rasterfile("working/01-aoi", f'{AOI_NAME}')

  if cru:

    # temds.datasources.dataset.YearlyDataset.from_crujra(
    #   year=1901, 
    #   data_path='working/02-arctic/cru-jra-fixed/crujra.arctic.v2.5.5d.1901.365d.noc.nc', 
    #   is_preprocessed=True, logger=log
    # )

    # Need this only one time to preprocess cru-jra files into temds format
    # takes care of naming issue...basically we need to flow thru 
    # temds.datasources.dataset.YearlyDataset.from_crujra once to get the names
    # and conversions....the prior stuff I had downloaded was processed with 
    # older code that didn't do it quite the same way, so the names of the variables
    # were not set to the standard ones...
    # data_list = []
    # for year in range(1901, 2024):
    #     X = temds.datasources.dataset.YearlyDataset.from_crujra(
    #         year=year, 
    #         data_path=f'working/02-arctic/cru-jra-fixed/crujra.arctic.v2.5.5d.{year}.365d.noc.nc', 
    #         is_preprocessed=True, 
    #         logger=log)
    #     data_list.append(X)
    # cru_arctic = temds.datasources.timeseries.YearlyTimeSeries(data_list, logger=log, in_memory=False)
    # cru_arctic.save("working/02-arctic/cru-jra-fixed-temds/", name_pattern=f"arctic_cru-jra_{{year}}.nc", zlib=True, complevel=1, overwrite=True)


    # # This loads from the small cropped area - but doesn't work due to variable names
    # data_list = []
    # for year in range(1901, 2024):
    #     X = temds.datasources.dataset.YearlyDataset.from_crujra(
    #         year=year, 
    #         data_path=f'working/02-{AOI_NAME}/{AOI_NAME}_cru/{AOI_NAME}_cru_{year}.nc', 
    #         is_preprocessed=True, 
    #         logger=log)
    #     data_list.append(X)
    # cru = temds.datasources.timeseries.YearlyTimeSeries(data_list, logger=log, in_memory=True)
    # cru.save(f"working/02-{AOI_NAME}/{AOI_NAME}_cru/", name_pattern=f'{AOI_NAME}_cru_{{year}}.nc', overwrite=True, complevel=1)

    # SLOW. This loads from the huge arctic files crops out the AOI and saves.
    cru_arctic = temds.datasources.timeseries.YearlyTimeSeries(
      Path('working/02-arctic/cru-jra-fixed-temds/'),
      logger=log,
      in_memory=False,
    )
    cru = cru_arctic.get_by_extent(*(aoi.get_raster_extent().iloc[0].values),extent_crs=aoi.aoi.crs, resolution=4000, in_memory=True)
    cru.save(f"working/02-{AOI_NAME}/{AOI_NAME}_cru/", name_pattern=f'{AOI_NAME}_cru_{{year}}.nc', overwrite=True, complevel=1)


  if wc:
    wc = temds.datasources.dataset.TEMDataset.from_worldclim(
      data_path='working/00-download/worldclim', 
      extent_raster=f'working/01-aoi/{AOI_NAME}/{AOI_NAME}_6931_4000m.tiff',
      download=False, 
      version='2.1', 
      resolution='30s', 
      in_vars='all',
      logger=log, 
    )
    wc.save(f"working/02-{AOI_NAME}/{AOI_NAME}_wc_6931_4000m.nc", overwrite=True)

  if veg:
    veg = temds.datasources.dataset.TEMDataset.from_vegetation(
      data_path='working/00-download/vegetation/',
      extent_raster=f'working/01-aoi/{AOI_NAME}/{AOI_NAME}_6931_4000m.tiff',
      download=False,
      logger=log,
    )
    veg.save(f'working/02-{AOI_NAME}/{AOI_NAME}_veg.nc', 
                overwrite=True, fill_value=np.int32(-9999), missing_value=np.int32(-9999))


  if topo:
    topo = temds.datasources.dataset.TEMDataset.from_topo(
      data_path='working/00-download/topo/',
      extent_raster=f'working/01-aoi/{AOI_NAME}/{AOI_NAME}_6931_4000m.tiff',
      download=False,
      logger=log,
    )
    topo.save(f'working/02-{AOI_NAME}/{AOI_NAME}_topo.nc',
              overwrite=True, fill_value=np.int32(-9999), missing_value=np.int32(-9999))

  if frifire:
    frifire = temds.datasources.dataset.TEMDataset.from_fri(
      #data_path='working/00-download/fri-fire/',
      synthetic=True,
      extent_raster_path=f'working/01-aoi/{AOI_NAME}/{AOI_NAME}_6931_4000m.tiff',
      #download=False,
      logger=log,
    )
    frifire.save(f'working/02-{AOI_NAME}/{AOI_NAME}_fri-fire.nc',
              overwrite=True, fill_value=np.int32(-9999), missing_value=np.int32(-9999))
    
  if hef:
    ## MAKE H FIRST, see below...
    ## NOTE, can't make this till we've exported the cru dataset to TEM to get
    ## the monthly size (or hard code multiply by 12 here...)
    ## NOTE: you gotta pass the actual time axis values...an xarray DataArray
    ## of some kind of time object.
    hef = temds.datasources.dataset.TEMDataset.from_historic_explicit_fire(
      #data_path='working/00-download/historic-explicit-fire/',
      synthetic=H.dataset['time'],
      #synthetic=cru[1901].dataset.time, # Pick up time axis from cru dataset
      extent_raster_path=f'working/01-aoi/{AOI_NAME}/{AOI_NAME}_6931_4000m.tiff',
      #download=False,
      logger=log,
    )
    hef.save(f'working/02-{AOI_NAME}/{AOI_NAME}_historic-ef.nc',
              overwrite=True, fill_value=np.int32(-9999), missing_value=np.int32(-9999))

  if soiltex:
    soiltex = temds.datasources.dataset.TEMDataset.from_soil_texture(
      data_path='working/00-download/soiltexture/',
      extent_raster=f'working/01-aoi/{AOI_NAME}/{AOI_NAME}_6931_4000m.tiff',
      download=False,
      logger=log,
    )
    soiltex.save(f'working/02-{AOI_NAME}/{AOI_NAME}_soiltex.nc',
              overwrite=True, fill_value=np.int32(-9999), missing_value=np.int32(-9999))

  if tile:

    tile_index = temds.aoitools.TileIndex(root = f"working/03-{AOI_NAME}/", aoimask = aoi)
    tile_index.calculate_tile_extents()
    tile_index.calculate_tile_gridsize()
    tile_index.cut_tileset(tile_index.calculate_tile_extents(), nickname='') # Leave nickname blank to avoid double AOI name in path
    tile_index.create_tile_index()


    hidx = 0
    vidx = 0
    rezx, rezy = tile_index.lookup_tile_resolution(hidx, vidx)
    tile = temds.tile.Tile( (hidx,vidx), tile_index.lookup_tile_extents(hidx,vidx), int(np.abs(rezx)), tile_index.aoimask.aoi.crs, buffer_px=0, logger=log)

    # load an existing directory....
    #tile.load_from_directory("working/03-vital-weevil-SE/tiles/H00_V00/")

    # make from raw ingredients...  
    tile.import_and_normalize('worldclim', wc)
    tile.import_and_normalize('veg', veg)
    tile.import_and_normalize('topo', topo)
    tile.import_and_normalize('soiltex', soiltex)
    tile.import_and_normalize('fri-fire', frifire)
    tile.import_and_normalize('historic-ef', hef)  # <-- DO THIS LATER! 
    tile.import_and_normalize('cru', cru)

    # If you've already downsclaled cru, you can load that directly instead of
    # doing the downscaling step again.
    #tile.import_and_normalize('cru-downscaled', cru_downscaled)


    start_year = 1970
    tile.calculate_climate_baseline(start_year, start_year + 30, 'cru-baseline', 'cru')
    tile.calculate_correction_factors('cru-baseline','worldclim', temds.climate_variables.DOWNSCALE_SAFE, 'cru-delta-cf')

    variables_ds = ['tair_avg', 'tair_max', 'tair_min', 'prec', 'nirr', 'wind', 'vapo', 'winddir']
    tile.downscale_timeseries('cru-downscaled', 'cru', 'cru-delta-cf', variables_ds, False)

    # Looking pretty good at this point. One small issue, the bottom row of pixels
    # for veg, topo, cru-downscale, cru-delta-cf are all off...initial tracing
    # points toward something in import and normalize?
    # the files in step 02 seem fine...but once in the tile, the last row is wrong.
    # The 


    # First, go ahead and export the dataset (tile) to a TEM format. (Full size
    # of the AOI). Put this in one of the locations (dvmdostem-dev container or
    # Field-To-Model container)
    #
    # Then run the extract pixel function to get the single pixel netcdf....
    # Put this in the Field-To-Model container and see if we can run it...
    # Re: names, the 

    #    The region used to make          the NGEE Site
    #    a multi-pix dataset                 
    #     AOI_NAME=modex26-TLK          SITE-ID=AK-TLK
    

    # At the end once it works:
    #  1) put it in the ../field-to-model-inputdata/TEM/ directory.
    #  2) new branch, commit the new files
    #  3) push to github
    #  4) make PR to merge to main repo, merge it.
    #  5) run the docker run ... get_inputdata command 

    # Use this for inserting to Model container
    #DIR = f'../Field-to-Model/model_examples/TEM/{AOI_NAME}/'

    # Use this for inserting into the field-to-model-inputdata repo
    DIR = f'../field-to-model-inputdata/TEM/{AOI_NAME}/'

    # use this for inserting to dvmdostem-dev container
    #DIR = '../dvmdostem-input-catalog/sample-temds/{AOI_NAME}/H{hidx:02d}_V{vidx:02d}/'.format(AOI_NAME=AOI_NAME, hidx=hidx, vidx=vidx)
    !mkdir -p {DIR}

    co2 = tile.to_TEM('co2')
    co2.to_netcdf(Path(DIR, "co2.nc"))

    T = tile.to_TEM('topo')
    T['topo_data'].to_netcdf(Path(DIR, 'topo.nc'))
    T['drainage_data'].to_netcdf(Path(DIR, 'drainage.nc'))

    V = tile.to_TEM('veg')
    V.to_netcdf(Path(DIR, 'vegetation.nc'))

    S = tile.to_TEM('soiltex')
    S.to_netcdf(Path(DIR, 'soil-texture.nc'))

    H = tile.to_TEM('cru-downscaled')
    H.dataset['Y'] = np.arange(H.dataset.sizes['y'])
    H.dataset['X'] = np.arange(H.dataset.sizes['x'])  
    H.save(Path(DIR, 'historic-climate.nc'), overwrite=True)

    F = tile.to_TEM('fri-fire')
    F.to_netcdf(Path(DIR, 'fri-fire.nc'))

    HEF = tile.to_TEM('historic-ef')
    HEF['time'] = H.dataset['time']
    HEF.to_netcdf(Path(DIR, 'historic-explicit-fire.nc'))

    import pandas as pd
    P = H.dataset.copy()
    P['time'] = H.dataset['time'] + pd.Timedelta(days=365)*(H.dataset['time'].size/12)
    P.to_netcdf(Path(DIR, 'projected-climate.nc'))

    PEF = HEF.copy()
    PEF['time'] = HEF['time'] + pd.Timedelta(days=365)*(HEF['time'].size/12)
    PEF.to_netcdf(Path(DIR, 'projected-explicit-fire.nc'))

    # DONT USE THIS, IT CAUSES PROBLEMS LATER
    # mask = np.ones( (tile.data['veg'].dataset.sizes['y'], 
    #                 tile.data['veg'].dataset.sizes['x']), dtype=np.int64)
    # R = xr.Dataset( {'run': ( ('Y','X'), mask)} )
    # R.to_netcdf(Path(DIR, 'run-mask.nc'), 'w')




    # !pip install -e /Users/tobeycarman/Documents/SEL/dvm-dos-tem/pyddt
    # For some reason, can't import here, but the cmd line stuff works...
    #import pyddt

    # This does not work...sets whole mask to 0
    #!pyddt-runmask --conform-mask-to-inputs {DIR} {DIR}/run-mask.nc



    # This gets the wrong size...the AOI is bigger than the tile. We need to get the
    # actual tile size here, the ubuffered tile size...
    # aoi.to_rasterfile(Path(DIR), f'') # Puts out a tiff
    # A = rxr.open_rasterio(Path(DIR, '_6931_4000m.tiff'))
    # A = A.rename({'band':'run', 'x':'X', 'y':'Y'})
    # A.to_netcdf(Path(DIR, 'run-mask.nc'))



import xarray as xr
import numpy as np

def extract_nearest_pixel_0(netcdf_file, target_lat, target_lon, output_file=None):
    """
    Extract a single pixel from NetCDF file nearest to given coordinates.
    Preserves all original dimensions but with y,x dimensions of size 1.
    
    Parameters:
    -----------
    netcdf_file : str
        Path to input NetCDF file
    target_lat : float
        Target latitude in degrees
    target_lon : float  
        Target longitude in degrees
    output_file : str, optional
        Path for output NetCDF file. If None, returns xarray Dataset
        
    Returns:
    --------
    xarray.Dataset or None
        Dataset with single pixel if output_file is None, otherwise saves to file
    """
    # Open the dataset
    ds = xr.open_dataset(netcdf_file)
    
    # Calculate distance from target coordinates to all grid points
    lat_diff = ds['lat'] - target_lat  
    lon_diff = ds['lon'] - target_lon
    
    # Simple Euclidean distance in lat/lon space
    distances = np.sqrt(lat_diff**2 + lon_diff**2)
    
    # Find the indices of minimum distance
    min_indices = np.unravel_index(np.argmin(distances.values), distances.shape)
    y_idx, x_idx = min_indices
    print(f"Nearest pixel indices: y={y_idx}, x={x_idx} with distance {distances.values[y_idx, x_idx]:.6f} degrees")
    print(f"++++++++++++++++++++++")

    # Extract the single pixel using isel but keep dimensions by using slice
    # This preserves the dimension structure but makes y,x dimensions size 1
    pixel_data = ds.isel(y=slice(y_idx, y_idx+1), x=slice(x_idx, x_idx+1))
    
    # Add metadata about the extraction
    pixel_data.attrs['extracted_from'] = netcdf_file
    pixel_data.attrs['target_lat'] = target_lat
    pixel_data.attrs['target_lon'] = target_lon
    pixel_data.attrs['actual_lat'] = float(ds['lat'].isel(y=y_idx, x=x_idx).values)
    pixel_data.attrs['actual_lon'] = float(ds['lon'].isel(y=y_idx, x=x_idx).values)
    pixel_data.attrs['pixel_indices'] = f"y={y_idx}, x={x_idx}"
    
    if output_file:
        # Save to file
        pixel_data.to_netcdf(output_file)
        print(f"Pixel data saved to {output_file}")
        print(f"Target coordinates: {target_lat}°N, {target_lon}°E")
        print(f"Actual coordinates: {pixel_data.attrs['actual_lat']:.6f}°N, {pixel_data.attrs['actual_lon']:.6f}°E")
        print(f"Output dimensions: y={pixel_data.dims['y']}, x={pixel_data.dims['x']}")
        return None
    else:
        return pixel_data
    



def extract_nearest_pixel_1(netcdf_file, target_lat, target_lon, output_file=None):
    """
    Extract a single pixel from NetCDF file nearest to given coordinates.
    Preserves all original dimensions but with y,x dimensions of size 1.
    Maintains proper geo-referencing for GIS software.
    
    Parameters:
    -----------
    netcdf_file : str
        Path to input NetCDF file
    target_lat : float
        Target latitude in degrees
    target_lon : float  
        Target longitude in degrees
    output_file : str, optional
        Path for output NetCDF file. If None, returns xarray Dataset
        
    Returns:
    --------
    xarray.Dataset or None
        Dataset with single pixel if output_file is None, otherwise saves to file
    """
    # Open the dataset
    ds = xr.open_dataset(netcdf_file)
    
    # Calculate distance from target coordinates to all grid points
    lat_diff = ds['lat'] - target_lat  
    lon_diff = ds['lon'] - target_lon
    
    # Simple Euclidean distance in lat/lon space
    distances = np.sqrt(lat_diff**2 + lon_diff**2)
    
    # Find the indices of minimum distance
    min_indices = np.unravel_index(np.argmin(distances.values), distances.shape)
    y_idx, x_idx = min_indices
    print(f"Nearest pixel indices: y={y_idx}, x={x_idx} with distance {distances.values[y_idx, x_idx]:.6f} degrees")
    
    # Extract the single pixel using isel but keep dimensions by using slice
    # This preserves the dimension structure but makes y,x dimensions size 1
    pixel_data = ds.isel(y=slice(y_idx, y_idx+1), x=slice(x_idx, x_idx+1))
    
    # Also reduce X and Y coordinate arrays to length 1 if they exist
    if 'X' in pixel_data.coords and len(pixel_data['X']) > 1:
        pixel_data = pixel_data.isel(X=slice(x_idx, x_idx+1))
    if 'Y' in pixel_data.coords and len(pixel_data['Y']) > 1:
        pixel_data = pixel_data.isel(Y=slice(y_idx, y_idx+1))
    
    # Ensure spatial_ref is preserved for geo-referencing
    if 'spatial_ref' in ds.variables:
        pixel_data['spatial_ref'] = ds['spatial_ref']
        
    # Update the GeoTransform attribute for the single pixel
    if 'spatial_ref' in pixel_data.variables and hasattr(pixel_data['spatial_ref'], 'GeoTransform'):
        # Parse the original GeoTransform
        original_gt = pixel_data['spatial_ref'].attrs.get('GeoTransform', '')
        if original_gt:
            gt_parts = [float(x) for x in original_gt.split()]
            if len(gt_parts) == 6:
                # Update GeoTransform for the extracted pixel location
                # gt_parts = [top_left_x, pixel_width, rotation1, top_left_y, rotation2, pixel_height]
                pixel_x = float(pixel_data['x'].values[0])
                pixel_y = float(pixel_data['y'].values[0])
                
                # Update top-left coordinates to the extracted pixel
                gt_parts[0] = pixel_x - gt_parts[1]/2  # x - pixel_width/2
                gt_parts[3] = pixel_y - gt_parts[5]/2  # y - pixel_height/2
                
                new_geotransform = ' '.join([str(x) for x in gt_parts])
                pixel_data['spatial_ref'].attrs['GeoTransform'] = new_geotransform
    
    # Add metadata about the extraction
    pixel_data.attrs['extracted_from'] = netcdf_file
    pixel_data.attrs['target_lat'] = target_lat
    pixel_data.attrs['target_lon'] = target_lon
    pixel_data.attrs['actual_lat'] = float(ds['lat'].isel(y=y_idx, x=x_idx).values)
    pixel_data.attrs['actual_lon'] = float(ds['lon'].isel(y=y_idx, x=x_idx).values)
    pixel_data.attrs['pixel_indices'] = f"y={y_idx}, x={x_idx}"
    
    if output_file:
        # Save to file with proper encoding for geo-referencing
        encoding = {}
        # Preserve important attributes for spatial_ref
        if 'spatial_ref' in pixel_data.variables:
            encoding['spatial_ref'] = {'_FillValue': None}
            
        pixel_data.to_netcdf(output_file, encoding=encoding)
        print(f"Pixel data saved to {output_file}")
        print(f"Target coordinates: {target_lat}°N, {target_lon}°E")
        print(f"Actual coordinates: {pixel_data.attrs['actual_lat']:.6f}°N, {pixel_data.attrs['actual_lon']:.6f}°E")
        #print(f"Output dimensions: y={pixel_data.dims['y']}, x={pixel_data.dims['x']}")
        # if 'X' in pixel_data.dims:
        #     print(f"X dimension: {pixel_data.dims['X']}")
        # if 'Y' in pixel_data.dims:
        #     print(f"Y dimension: {pixel_data.dims['Y']}")
        return None
    else:
        return pixel_data
    


def extract_pixel_by_indices(netcdf_file, y_idx, x_idx, output_file=None):
    """
    Extract a single pixel from NetCDF file using known y,x indices.
    Preserves all original dimensions but with y,x dimensions of size 1.
    Maintains proper geo-referencing for GIS software.
    
    Parameters:
    -----------
    netcdf_file : str
        Path to input NetCDF file
    y_idx : int
        Y index of the pixel to extract
    x_idx : int
        X index of the pixel to extract
    output_file : str, optional
        Path for output NetCDF file. If None, returns xarray Dataset
        
    Returns:
    --------
    xarray.Dataset or None
        Dataset with single pixel if output_file is None, otherwise saves to file
    """
    # Open the dataset
    ds = xr.open_dataset(netcdf_file)
    
    # Validate indices
    if y_idx < 0 or y_idx >= ds.sizes['y']:
        raise ValueError(f"y_idx {y_idx} out of bounds for dimension of size {ds.sizes['y']}")
    if x_idx < 0 or x_idx >= ds.sizes['x']:
        raise ValueError(f"x_idx {x_idx} out of bounds for dimension of size {ds.sizes['x']}")
    
    print(f"Extracting pixel at indices: y={y_idx}, x={x_idx}")
    
    # Extract the single pixel using isel but keep dimensions by using slice
    # This preserves the dimension structure but makes y,x dimensions size 1
    pixel_data = ds.isel(y=slice(y_idx, y_idx+1), x=slice(x_idx, x_idx+1))
    
    # Also reduce X and Y coordinate arrays to length 1 if they exist
    if 'X' in pixel_data.coords and len(pixel_data['X']) > 1:
        pixel_data = pixel_data.isel(X=slice(x_idx, x_idx+1))
    if 'Y' in pixel_data.coords and len(pixel_data['Y']) > 1:
        pixel_data = pixel_data.isel(Y=slice(y_idx, y_idx+1))
    
    # Ensure spatial_ref is preserved for geo-referencing
    if 'spatial_ref' in ds.variables:
        pixel_data['spatial_ref'] = ds['spatial_ref']
        
    # Update the GeoTransform attribute for the single pixel
    if 'spatial_ref' in pixel_data.variables and hasattr(pixel_data['spatial_ref'], 'GeoTransform'):
        # Parse the original GeoTransform
        original_gt = pixel_data['spatial_ref'].attrs.get('GeoTransform', '')
        if original_gt:
            gt_parts = [float(x) for x in original_gt.split()]
            if len(gt_parts) == 6:
                # Update GeoTransform for the extracted pixel location
                # gt_parts = [top_left_x, pixel_width, rotation1, top_left_y, rotation2, pixel_height]
                pixel_x = float(pixel_data['x'].values[0])
                pixel_y = float(pixel_data['y'].values[0])
                
                # Update top-left coordinates to the extracted pixel
                gt_parts[0] = pixel_x - gt_parts[1]/2  # x - pixel_width/2
                gt_parts[3] = pixel_y - gt_parts[5]/2  # y - pixel_height/2
                
                new_geotransform = ' '.join([str(x) for x in gt_parts])
                pixel_data['spatial_ref'].attrs['GeoTransform'] = new_geotransform
    
    # Add metadata about the extraction
    pixel_data.attrs['extracted_from'] = netcdf_file
    pixel_data.attrs['pixel_indices'] = f"y={y_idx}, x={x_idx}"
    
    # Add coordinate info if available
    if 'lat' in ds.variables and 'lon' in ds.variables:
        pixel_data.attrs['actual_lat'] = float(ds['lat'].isel(y=y_idx, x=x_idx).values)
        pixel_data.attrs['actual_lon'] = float(ds['lon'].isel(y=y_idx, x=x_idx).values)
    
    if output_file:
        # Save to file with proper encoding for geo-referencing
        encoding = {}
        # Preserve important attributes for spatial_ref
        if 'spatial_ref' in pixel_data.variables:
            encoding['spatial_ref'] = {'_FillValue': None}
            
        pixel_data.to_netcdf(output_file, encoding=encoding)
        print(f"Pixel data saved to {output_file}")
        print(f"Extracted pixel at indices: y={y_idx}, x={x_idx}")
        if 'actual_lat' in pixel_data.attrs:
            print(f"Coordinates: {pixel_data.attrs['actual_lat']:.6f}°N, {pixel_data.attrs['actual_lon']:.6f}°E")
        return None
    else:
        return pixel_data  
    

def create_runmask(input_dir, output_file=None, reference_file=None):
    """
    Create a runmask.nc file with 'run' variable set to all zeros.
    The dimensions are based on the X,Y dimensions from files in the input directory.
    
    Parameters:
    -----------
    input_dir : str
        Path to directory containing TEM input files
    output_file : str, optional
        Path for output runmask file. If None, saves as 'runmask.nc' in input_dir
    reference_file : str, optional
        Specific file to use for dimension reference. If None, uses first NetCDF file found
        
    Returns:
    --------
    str
        Path to the created runmask file
    """
    import os
    import glob
    import xarray as xr
    import numpy as np
    from pathlib import Path
    
    input_path = Path(input_dir)
    
    # Find NetCDF files in the directory
    nc_files = list(input_path.glob("*.nc"))
    if not nc_files:
        raise FileNotFoundError(f"No NetCDF files found in {input_dir}")
    
    # Use specified reference file or first file found
    if reference_file:
        ref_file = Path(reference_file)
        if not ref_file.exists():
            raise FileNotFoundError(f"Reference file {reference_file} not found")
    else:
        ref_file = nc_files[0]
    
    print(f"Using {ref_file.name} as reference for dimensions")
    
    # Open reference file to get dimensions
    with xr.open_dataset(ref_file) as ds:
        # Look for X,Y or x,y dimensions
        if 'X' in ds.dims and 'Y' in ds.dims:
            x_dim, y_dim = 'X', 'Y'
            x_size, y_size = ds.dims['X'], ds.dims['Y']
        elif 'x' in ds.dims and 'y' in ds.dims:
            x_dim, y_dim = 'x', 'y'
            x_size, y_size = ds.dims['x'], ds.dims['y']
        else:
            raise ValueError(f"Could not find X,Y or x,y dimensions in {ref_file}")
        
        # Get coordinate values if they exist
        if x_dim in ds.coords:
            x_coords = ds[x_dim].values
        else:
            x_coords = np.arange(x_size)
            
        if y_dim in ds.coords:
            y_coords = ds[y_dim].values
        else:
            y_coords = np.arange(y_size)
        
        # Copy spatial reference information if it exists
        spatial_ref = None
        if 'spatial_ref' in ds.variables:
            spatial_ref = ds['spatial_ref']
    
    print(f"Creating runmask with dimensions: {y_dim}={y_size}, {x_dim}={x_size}")
    
    # Create runmask array (all zeros)
    run_data = np.zeros((y_size, x_size), dtype=np.int32)
    
    # Create dataset
    coords = {y_dim: y_coords, x_dim: x_coords}
    runmask_ds = xr.Dataset({
        'run': xr.DataArray(
            run_data, 
            dims=[y_dim, x_dim], 
            coords=coords,
            attrs={
                'long_name': 'run mask',
                'description': 'Mask indicating which pixels to run (1=run, 0=skip)',
                '_FillValue': -9999
            }
        )
    }, coords=coords)
    
    # Add spatial reference if it existed in reference file
    if spatial_ref is not None:
        runmask_ds['spatial_ref'] = spatial_ref
        # Update run variable to reference spatial_ref
        runmask_ds['run'].attrs['grid_mapping'] = 'spatial_ref'
    
    # Add global attributes
    runmask_ds.attrs.update({
        'title': 'TEM Run Mask',
        'description': f'Run mask created from dimensions of {ref_file.name}',
        'created_from': str(ref_file)
    })
    
    # Set output file path
    if output_file is None:
        output_file = input_path / 'run-mask.nc'
    else:
        output_file = Path(output_file)
    
    # Save to file
    encoding = {'run': { 'dtype': 'int32'}}
    if spatial_ref is not None:
        encoding['spatial_ref'] = {'_FillValue': None}
    
    runmask_ds.to_netcdf(output_file, encoding=encoding)
    print(f"Runmask saved to {output_file}")
    
    return str(output_file)

# Example usage:
# create_runmask('../dvmdostem-input-catalog/sample-temds/modex26_1x1_AK-UTQ/')
# or specify output file:
# create_runmask('../dvmdostem-input-catalog/sample-temds/modex26_1x1_AK-UTQ/', 'custom_runmask.nc')
# or specify reference file:
# create_runmask('../dvmdostem-input-catalog/sample-temds/modex26_1x1_AK-UTQ/', reference_file='vegetation.nc')




import os
import glob
from pathlib import Path
import shutil

## Assumes that you have already created the multi-pixel TEM dataset for the
## desired region (e.g., modex26-TLK) using the temds.tile.Tile functionality
## above. Once you have that multi-pixel dataset, you can use this code to
## extract out a single pixel dataset for a specific site (e.g., AK-TFS-IMC)
## to put into the field-to-model-inputdata repo. Assumes that the extracted
## pixel dataset will be put in to a directory named modex26_1x1_{SITE_ID}.
## that is alongside the existing modex26-TLK directory.

DIR = f"../field-to-model-inputdata/TEM/modex26-NSweden/"
#SITE_ID = 'AK-TFS-IMC'; LAT=68.56066; LON=-149.34047
#SITE_ID = 'AK-UTQ'; LAT=71.3; LON=-156.60
SITE_ID = 'SE-ASRS'; LAT=68.35; LON=18.78

for f in glob.glob(f"{DIR}/*.nc"):
  src = Path(f)
  dst = Path(src.parent.parent, f'modex26_1x1_{SITE_ID}', src.name)
  dst.parent.mkdir(parents=True, exist_ok=True)
  print("Source:", src, )
  print("Destination:", dst)   
  if 'historic-climate' in src.name:
    extract_nearest_pixel_1(f, LAT, LON, dst)
  if 'co2' in src.name:
    shutil.copy(f, dst)
  else:
    print("Do me next time...", src.name)
    extract_pixel_by_indices(f, 50, 57, dst)

create_runmask(Path(dst.parent), output_file=Path(dst.parent, 'run-mask.nc'), reference_file=dst)

