"""
Sub Utility Helpers for CLI
---------------------------

"""
from pathlib import Path
from collections import UserDict

import yaml

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
        print(root, key1, key2)
    
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
