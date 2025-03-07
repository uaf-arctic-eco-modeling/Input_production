"""
"""
import requests
import zipfile

from pathlib import Path


# __COMPRESSED_TYPES__ = ['.zip']#, '.gz']

class RemoteZipPedanticError(Exception):
    pass

class RemoteZip(object):
    def __init__(self, url, verbose=False, pedantic=False):
        self.url = url
        self.local_file = None
        self.verbose = verbose
        self.pedantic=pedantic

    def download(self, location, overwrite=False):
        location = Path(location)
        self.local_file = Path(location, Path(self.url).name)
        
        if not self.local_file.exists() or overwrite:
            if self.verbose: print(f"downloading: {self.url}" )
            location.mkdir(parents=True, exist_ok=True)

            r = requests.get(self.url)
            with self.local_file.open('wb') as new_file:
                new_file.write(r.content)
        else:
            if self.verbose:
                print(f"Local file exists {self.local_file}" )
            if self.pedantic:
                raise RemoteZipPedanticError(
                    f"Local file exists {self.local_file}"
                )

        return self.local_file

    # def uncompress(self):
    #     if self.local_file is None:
    #         return 0# to exception

    #     if not self.local_file.suffix in __COMPRESSED_TYPES__:
    #         return self.local_file


    #     if self.local_file.suffix == '.zip':
    #         return self.unzip()
    def unzip(self, where = None):
        if self.local_file is None:
            return 0# to exception
        if self.verbose: print(f"Extracting {self.local_file}")
        with zipfile.ZipFile(self.local_file, 'r') as zip_ref:
          if where is None:
            where = Path(self.local_file.parent, self.local_file.stem)
          if self.verbose: print(f"Extracting {where=}")
          zip_ref.extractall(where)
        return where
    

    