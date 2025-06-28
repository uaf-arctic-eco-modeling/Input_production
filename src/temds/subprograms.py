"""
Sub Utility Helpers for CLI
---------------------------

"""
from pathlib import Path
from collections import UserDict
import multiprocessing

import yaml

from . import crujra
from . import AOIMask
from . import util
from .worldclim import WORLDCLIM_VARS, WORLDCLIM_URL_PATTERN, WorldClim

DATA_SOURCES = [
    'worldclim',
    'crujra',
]


DEFAULT_DOWNLOAD_LOCATIONS = {
    'worldclim': WORLDCLIM_URL_PATTERN
}


class Config(UserDict):
    ## need to add init so we can validate config
    def path_to(self, key1, key2=None):
        root = './'
        
        if 'root' in self.data['global']['directories']:
            root = self.data['global']['directories']['root']

        if 'root' == key1:
            return Path(root)
    
        if not key2 is None:
            return Path(
                root,
                self.data['global']['directories'][key1],
                key2
            )

        return Path(
            root,
            self.data['global']['directories'][key1]
        )

    def url_for(self, source, var=None, cached=False):
        url = self[source]['url']

        if 'default' == url:
            url = DEFAULT_DOWNLOAD_LOCATIONS[source]
        return url

def download(what, config='', save_to='./download', url_pattern='default', overwrite=False):
    """
    """
    if what not in DATA_SOURCES:
        print('ERROR unsupported data source')
        return 0
    if config != '':
        with Path(config).open('r') as fd:
            config = Config(yaml.safe_load(fd))

    else: 
        config = Config({
            'global': {
                'overwrite': overwrite,
                'directories':{
                    'download': save_to
                },
            },
            'aoi': {
                'name':'AOIname',
                'raster': None
            },
            'worldclim': {
                'url': url_pattern,
                'vars': 'all'#TODO add argument
            }
        })

    url = config.url_for(what)
    overwrite = config['global']['overwrite']
    save_to = config.path_to('download', what)

    print(f"Downloading {what} from {url} [overwrite: {overwrite}]")
    print(f"Saving {what} to {save_to} ")

    if 'worldclim' == what:
        vars = config['worldclim']['vars']
        if 'all' == vars:
            vars = WORLDCLIM_VARS
       
        data = WorldClim(
            url,
            config['aoi']['raster'],
            True,  
            local_location=save_to,  
            _vars=vars
        )

    save_to = config.path_to('preprocessed', what)
    aoi_name = config['aoi']['name']
    save_to.mkdir(parents=True, exist_ok=True)
    data.save(
        Path(save_to, f'{what}-{aoi_name}.nc'), 
        overwrite=overwrite
    )
    return data


def setup_directories(*args, **kwargs):
    if len(args) == 1:
        with Path(args[0]).open('r') as fd:
            config = Config(yaml.safe_load(fd))

    else: 
        ## Not fixing as it needs to be refactored with class Coonfig
        # config = Config({
        #     'global': {
        #         'directories':{
        #             'root': kwargs['root'], # TODO refac
        #             # 'aoi': aoi,
        #             # 'download': download,
        #             # 'preprocessed': preprocessed,
        #             # 'tiles': tiles,
        #             # 'final': final
        #         },
        #     },
        # })
        pass


    for dir in config['global']['directories']:
        config.path_to(dir).mkdir(parents=True, exist_ok=True)
    if 'worldclim' in config.data:
        for dir in ['download', 'preprocessed']:
            config.path_to(dir, 'worldclim').mkdir(parents=True, exist_ok=True)


def bucketfill_cru():
    print("Not implemented yet...should do all the stuff to download masses of data and put it in the bucket")

def cru_load_crop_and_save(pdict):
    '''worker function - designed to be wrapped with some kind of multi processing thing'''
    buffered_aoi = pdict['buffered_aoi']
    year = pdict['year']
    cru = crujra.AnnualDaily(year, 'local_test_data', True, aoi_extent=buffered_aoi)
    cru.save(f"working/cru-arctic/crujra.arctic.v2.5.5d.{year}.365d.noc.nc")


def spatial_crop_cru():
    print("""Spatially cropping the cru data. Use the AOIMask extents to 
          chop off the arctic portion of the cru data and combine all
          variables into a single file for each year. Save the files to a new
          folder. Use a processing pool to process more than one year at a time.
          Small pool number because I think each process takes several GB of 
          memory.""")

    aoi_extent = AOIMask.AOIMask(root = 'working/')
    aoi_extent.load_from_vector('working/aoi_4326/aoi_4326.shp')

    minx, miny, maxx, maxy = aoi_extent.aoi_vector.bounds.values[0]

    buffered_aoi = util.buffer_extent([minx, maxx, miny, maxy], 0.1, 6)

    Path.mkdir(Path('working/cru-arctic/'), exist_ok=True)

    # start 3 worker processes
    with multiprocessing.Pool(processes=3) as pool:

        plist = [dict(buffered_aoi=buffered_aoi, year=y) for y in range(1901, 1904)]
        # print "[0, 1, 4,..., 81]"
        pool.map(cru_load_crop_and_save, plist)

    # for year in range(1901, 1904):
    #   cru = crujra.CRU_JRA_daily(year, 'local_test_data', True, aoi_extent=buffered_aoi)
    #   cru.save(f"working/cru-arctic/crujra.arctic.v2.5.5d.{year}.365d.noc.nc")


