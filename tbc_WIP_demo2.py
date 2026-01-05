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
    tile.load_from_directory("working/03-vital-weevil-SE/tiles/H00_V00/")

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


    DIR = '../dvmdostem-input-catalog/sample-temds/{AOI_NAME}/H{hidx:02d}_V{vidx:02d}/'.format(AOI_NAME=AOI_NAME, hidx=hidx, vidx=vidx)
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

    mask = np.ones( (tile.data['veg'].dataset.sizes['y'], 
                    tile.data['veg'].dataset.sizes['x']), dtype=np.int64)
    R = xr.Dataset( {'run': ( ('Y','X'), mask)} )
    R.to_netcdf(Path(DIR, 'run-mask.nc'), 'w')

    

    # !pip install -e /Users/tobeycarman/Documents/SEL/dvm-dos-tem/pyddt
    # For some reason, can't import here, but the cmd line stuff works...
    #import pyddt

    # This does not work...sets whole mask to 0
    #!pyddt-runmask --conform-mask-to-inputs {DIR} {DIR}/run-mask.nc


    !

    # This gets the wrong size...the AOI is bigger than the tile. We need to get the
    # actual tile size here, the ubuffered tile size...
    # aoi.to_rasterfile(Path(DIR), f'') # Puts out a tiff
    # A = rxr.open_rasterio(Path(DIR, '_6931_4000m.tiff'))
    # A = A.rename({'band':'run', 'x':'X', 'y':'Y'})
    # A.to_netcdf(Path(DIR, 'run-mask.nc'))










X
X.data
X.dataset
X.save("/tmp/forTEM.nc")
X.save("/tmp/historic-climate.nc")
tile
pwd
ls ../dvm-dos-tem/demo-data/cru-ts40_ar5_rcp85_ncar-ccsm4_toolik_field_station_10x10/
!ncdump -h ../dvm-dos-tem/demo-data/cru-ts40_ar5_rcp85_ncar-ccsm4_toolik_field_station_10x10/
!ncdump -h ../dvm-dos-tem/demo-data/cru-ts40_ar5_rcp85_ncar-ccsm4_toolik_field_station_10x10/drainage.nc
topo.
temds.dataset.TEMDataset(tile.data['topo'])
temds.datasources.dataset.TEMDataset(tile.data['topo'])
tile.data['topo'].dataset
V = tile.data['topo'].dataset
V.drop('TPI')
V.drop('TPI').drop('drainage_class')
V = tile.to_TEM('topo')
V = tile.to_TEM('topo')
V
tile.data['topo'].dataset['drainage_class']
tile.data['topo'].dataset.drop('elevation', 'TPI', 'slope', 'aspect')
tile.data['topo'].dataset.drop(['elevation', 'TPI', 'slope', 'aspect'])
V = tile.to_TEM('topo')
V
tile.data['veg']
tile.data['veg'].dataset
tile.data['veg'].dataset
!ncdump -h ../dvm-dos-tem/demo-data/cru-ts40_ar5_rcp85_ncar-ccsm4_toolik_field_station_10x10/
ls ../dvm-dos-tem/demo-data/cru-ts40_ar5_rcp85_ncar-ccsm4_toolik_field_station_10x10/
!ncdump -h ../dvm-dos-tem/demo-data/cru-ts40_ar5_rcp85_ncar-ccsm4_toolik_field_station_10x10/co2.nc
tile
tile.data['soiltex']
tile.data['soiltex'].data
tile.data['soiltex'].dataset
!ncdump -h ../dvm-dos-tem/demo-data/cru-ts40_ar5_rcp85_ncar-ccsm4_toolik_field_station_10x10/co2.nc
import matplotlib.pyplot as plt
import xarray as xr
xr.load_data('../dvm-dos-tem/demo-data/cru-ts40_ar5_rcp85_ncar-ccsm4_toolik_field_station_10x10/co2.nc')
xr.load_dataset('../dvm-dos-tem/demo-data/cru-ts40_ar5_rcp85_ncar-ccsm4_toolik_field_station_10x10/co2.nc')
co2 = xr.load_dataset('../dvm-dos-tem/demo-data/cru-ts40_ar5_rcp85_ncar-ccsm4_toolik_field_station_10x10/co2.nc')
co2.plot()
co2.variables['co2'].plot()
co2.variables['co2']
plt.plot(co2.variables['co2'])
plt.show()
!ncview ../dvm-dos-tem/demo-data/cru-ts40_ar5_rcp85_ncar-ccsm4_toolik_field_station_10x10/co2.nc
!ncdump  ../dvm-dos-tem/demo-data/cru-ts40_ar5_rcp85_ncar-ccsm4_toolik_field_station_10x10/co2.nc
xr.Dataset(data_vars={'co2':co2}, coords={'year':year})
            year = [1901, 1902, 1903, 1904, 1905, 1906, 1907, 1908, 1909, 1910, 1911, 
                1912, 1913, 1914, 1915, 1916, 1917, 1918, 1919, 1920, 1921, 1922, 1923, 
                1924, 1925, 1926, 1927, 1928, 1929, 1930, 1931, 1932, 1933, 1934, 1935, 
                1936, 1937, 1938, 1939, 1940, 1941, 1942, 1943, 1944, 1945, 1946, 1947, 
                1948, 1949, 1950, 1951, 1952, 1953, 1954, 1955, 1956, 1957, 1958, 1959, 
                1960, 1961, 1962, 1963, 1964, 1965, 1966, 1967, 1968, 1969, 1970, 1971, 
                1972, 1973, 1974, 1975, 1976, 1977, 1978, 1979, 1980, 1981, 1982, 1983, 
                1984, 1985, 1986, 1987, 1988, 1989, 1990, 1991, 1992, 1993, 1994, 1995, 
                1996, 1997, 1998, 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 
                2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 
                2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]
            co2 = [296.311, 296.661, 297.04, 297.441, 297.86, 298.29, 298.726, 299.163, 
                299.595, 300.016, 300.421, 300.804, 301.162, 301.501, 301.829, 302.154, 
                302.48, 302.808, 303.142, 303.482, 303.833, 304.195, 304.573, 304.966, 
                305.378, 305.806, 306.247, 306.698, 307.154, 307.614, 308.074, 308.531, 
                308.979, 309.401, 309.781, 310.107, 310.369, 310.559, 310.667, 310.697, 
                310.664, 310.594, 310.51, 310.438, 310.401, 310.41, 310.475, 310.605, 
                310.807, 311.077, 311.41, 311.802, 312.245, 312.736, 313.27, 313.842, 
                314.448, 315.084, 315.665, 316.535, 317.195, 317.885, 318.495, 318.935, 
                319.58, 320.895, 321.56, 322.34, 323.7, 324.835, 325.555, 326.55, 
                328.455, 329.215, 330.165, 331.215, 332.79, 334.44, 335.78, 337.655, 
                338.925, 340.065, 341.79, 343.33, 344.67, 346.075, 347.845, 350.055, 
                351.52, 352.785, 354.21, 355.225, 356.055, 357.55, 359.62, 361.69, 
                363.76, 365.83, 367.9, 368, 370.1, 372.2, 373.6943, 375.3507, 377.0071, 
                378.6636, 380.5236, 382.3536, 384.1336, 389.9, 391.65, 393.85, 396.52, 
                398.65, 400.83,
                404.41, 406.76, 408.72, 411.65, 414.21, 416.41, 418.53, 421.08, 424.61 ]
xr.Dataset(data_vars={'co2':co2}, coords={'year':year})
xr.Dataset(coords={'year':year})
xr.Dataset(co2, coords={'year':year})
xr.Dataset?
xr.Dataset(data_vars={'co2':(year,co2)}, coords={'year':year})
xr.Dataset(data_vars={'co2':((year),co2)}, coords={'year':year})
xr.Dataset(data_vars={'co2':('year',co2)}, coords={'year':year})
tile
co2 = tile.to_TEM('co2')
co2 = tile.to_TEM('co2')
co2 = tile.to_TEM('co2')
co2 = tile.to_TEM('co2')
type(co2)
co2.to_netcdf("../dvmdostem-workflows/test-temds/vital-weevil-SE/co2.nc")
!mkdir -p /Users/tobeycarman/Documents/SEL/dvmdostem-workflows/test-temds/vital-weevil-SE/
