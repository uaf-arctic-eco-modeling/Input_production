"""
Worldclim
---------

Metadata for worldclim dataset

See: for dataset details (for v2.1) 
https://www.worldclim.org/data/worldclim21.html

"""
from cf_units import Unit
from temds import climate_variables
from pathlib import Path

from ..logger import Logger
from .. import file_tools

import gc
from osgeo import gdal

NAME = 'worldclim'


## citation for worldclim 2.1 dataset
CITATION = (
    'Fick, S.E. and R.J. Hijmans, 2017. WorldClim 2: tem_dataset 1km spatial resolution' 
    ' climate surfaces for global land areas. International Journal of '
    ' Climatology 37 (12): 4302-4315.'
)


## REGISTER CLIMATE VARIABLES
climate_variables.register('tair_avg', NAME, 'tavg')
climate_variables.register('tair_min', NAME, 'tmin')
climate_variables.register('tair_max', NAME, 'tmax')
climate_variables.register('prec', NAME, 'prec')
climate_variables.register('nirr', NAME, 'srad')
climate_variables.register('wind', NAME, 'wind')
climate_variables.register('vapo', NAME, 'vapr')

## worldclim units are in downscale units except for
## srad/nirr 
climate_variables.register_source_unit('nirr', NAME, Unit('kJ m-2 day-1'))

VARS = climate_variables.aliases_for(NAME)

## these are degree seconds and degree minutes
## representing  form ~1 km2 to ~340 km2
RESOLUTIONS = ['30s', '2.5m', '5m', '10m']

class WorldclimURLError(Exception):
    """Raised if the url cannot be formatted"""
    pass

def name_for(variable, version='2.1', resolution='30s', month=None):
    if resolution not in RESOLUTIONS:
        raise WorldclimURLError('Invalid Resolution')

    if not variable in VARS:
        raise WorldclimURLError('Invalid variable')

    if month is None:
        return f'wc{version}_{resolution}_{variable}'
    else:
        return f'wc{version}_{resolution}_{variable}_{month:02d}'

def url_for(variable, version='2.1', resolution='30s'):
    v_us = version.replace('.','_')
    name = name_for(variable, version, resolution)
    return f'https://geodata.ucdavis.edu/climate/worldclim/{v_us}/base/{name}.zip'


def download(where, in_vars, version, resolution, overwrite = False, logger=Logger() ):
    for var in in_vars:
        logger.info(f'worldclim.download: Downloading data.')
        url = url_for(var, version, resolution)
        logger.debug(f'worldclim.download: downloading {url}')
        file_tools.download(url, where, overwrite)

def prepare(where, in_vars, version, resolution, overwrite = False, logger=Logger() ):
    completed = {}
    for var in in_vars:
        var_dir = name_for(var, version, resolution)
        in_dir = Path(f'{where}/{var_dir}')
        if not in_dir.exists():
            archive = Path(f'{where}/{var_dir}.zip')
            logger.debug(f'worldclim.unzip: unzipping {archive}')
            file_tools.extract(archive, in_dir)
        completed[var] = in_dir
    return completed



    new = TEMDataset.from_region(
            region, 
        in_vars=in_vars, 
        ds_time_dim=MONTH_START_DAYS, 
        logger=logger,
        buffer_px=0
    )
    # new the TEMDataset object does not seem to be geo-refd at this point...
    # but new.dataset is geo-refed...and it looks like the right spot too.
    logger.info(f"{func_name}: Initialization complete")
    
    logger.info(
        f'{func_name}: Running gdal.Warp to extent {region.get_extent()} on all data'
    )


    result = region.empty_gdal_dataset()
    for var in in_vars:
        cv = climate_variables.lookup_alias(NAME, var)
        unit = cv.std_unit.name
        v_name = cv.name

        ## this is inplace as opposed to assign_attrs
        tem_dataset.dataset[var].attrs.update(units=unit, name=v_name)

        in_dir = completed[var]
        for month in range(1,13):
            idx = month-1
            name = name_for(
                var, version, resolution, month
            )
            data_raster = Path(in_dir, f'{name}.tif')
            
            logger.debug((
                f'{func_name}: loading {var} data from {data_raster} for '
                f'month {month} at index {idx}'
            ))

            gdal.Warp(
                result, data_raster, 
                resampleAlg=resample_alg,
                dstNodata=-3.4e+38,
                outputType=gdal.GDT_Float32,
            )
            pixels = result.ReadAsArray()

            pixels[pixels <= -3e30] = np.nan # fix
            
            tem_dataset.dataset[var][idx] = pixels # 0based index
            [gc.collect(i) for i in range(2)]

    # any Unit conversions
        source = 'worldclim'
        for stn, wcn in climate_variables.aliases_for(source, 'dict').items():
            
            if climate_variables.has_conversion(stn, source):
                logger.info(f'{func_name}: converting units for {wcn} to {stn}')
                new.dataset[wcn].values = climate_variables.to_std_units(
                    new.dataset[wcn].values, stn, source
                )

        

        logger.info(f'{func_name}: Renaming variables to standard names...')
        logger.debug(f'{func_name}: Before rename: {list(new.dataset.data_vars)}')
        logger.debug(f'{func_name}: Using aliases: {climate_variables.aliases_for(worldclim.NAME, "dict_r")}')        
        new.dataset = new.dataset.rename(
            climate_variables.aliases_for(worldclim.NAME, 'dict_r')
        )
        logger.debug(f'{func_name}: After rename: {list(new.dataset.data_vars)}')