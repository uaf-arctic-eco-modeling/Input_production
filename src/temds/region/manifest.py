"""
Maniifest
---------

object to represent the manifest

TODO:
- Checks for required items(i.e. mask, boundary) at save/load 
- Verify that user dict update works and does not need to be overloaded

"""
from collections import UserDict
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
        return new
        

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
      
