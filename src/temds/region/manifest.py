"""
Maniifest
---------

object to represent the manifest

TODO:
- Checks for required items(i.e. mask, boundary) at save/load 
- Verify that user dict update works and does not need to be overloaded

"""
from collections import UserDict
import glob
from pathlib import Path

import yaml

class Manifest(UserDict):
    """Manifest is a dict like structure that can be serialized or loaded
    from a yml file

    Attributes
    ----------
    data: Dict
        internal data
    """
    def __init__(self):
        """Empty manifest data is created with a single sub dictionary for data
        """
        self.data = {
            'data': {}
        }

    @classmethod
    def from_directory(cls, where: str | Path):
        """Create from directory. THis looks for all the files in a directory
        and creates a manifest with those files listed under the 'data' key. It
        then looks for a manifest.yml file in the directory, and if it exists it
        loads that and updates the manifest with any additional information in
        the file. This allows users to create a manifest from a directory of
        files, and then add additional information to the manifest by editing
        the manifest.yml file.

        Parameters
        ----------
        where: Path like
            directory to look for manifest.yml file in

        Returns
        -------
        Manifest
        """

        new = cls()
        where = Path(where)
        for file in where.glob('*.nc'):
            new['data'][file.stem] = str(file.name)

        if len(list(where.glob('*.tif'))) > 1:
            raise ValueError('Multiple tif files found in directory. Cannot determine which one to use as mask. Please remove extra tif files or specify mask in manifest.yml file.')
        for file in where.glob('*.tif'):
            new['mask'] = str(file.name)

        if len(list(where.glob('*.geojson'))) > 1:
            raise ValueError('Multiple geojson files found in directory. Cannot determine which one to use as boundary. Please remove extra geojson files or specify boundary in manifest.yml file.')
        for file in where.glob('*.geojson'):
            new['boundary'] = str(file.name)

        for file in where.glob('*nc.aux.xml'):
            pass
            # should use logging class here?
            #print(f'Ignoring aux file {file} in manifest creation....')


        for item in where.glob("*"):
            if item.is_dir():
                if item.stem in ['tem_export', 'tem-export']:
                    continue
                else:
                    new['data'][item.stem] = str(item.stem)
 
        manifest_file = where / 'manifest.yml'

        if manifest_file.exists():
            print("Manifest file found, loading manifest data from file and updating with found data...")
            with manifest_file.open('r') as fd:
                manifest_data = yaml.load(fd, yaml.Loader)
            manifest_data.update(new)

        with manifest_file.open('w') as fd:
            print("Saving manifest file...")
            yaml.safe_dump(manifest_data, fd, sort_keys=False)      


        return manifest_data

    @classmethod
    def from_file(cls, where: str | Path):
        """Create from yaml file

        Parameters
        ----------
        where: Path like
            yaml file to load

        Returns
        -------
        Manifest
        """
        new = cls()
        with Path(where).open('r') as fd:
            new.data = yaml.load(fd, yaml.Loader)

        if new.data['data'] is None:
            new.data['data'] = {}
        return new
        
    def add_dataset(self, name, file):
        self.data['data'][name] = file

    def to_file(self, where: str | Path):
        """Saves manifest to yml file

        Parameters
        ----------
        where: Path like
            yaml file to load
        """
        with Path(where).open('w') as fd:
            yaml.safe_dump(self.data, fd, sort_keys=False)

    # def update(self, new):
      
