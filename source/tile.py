"""
Tile
----



"""


class Tile(object):
    """
    """
    def __init__(self):
        """
        """
        self.data = {}# dictionary of data
                      # i.E {'crujra': crujra, ...}
        self.extent = None# aoi object, or a modified aoi object

    def load_from_directory(self, directory):
        """
        """
        pass

    def load_extent(self, extent_file):
        """
        """
        pass

    def load_data(self, data): #or (self, name, data)? or all?
        """
        """
        pass

    def save(self, where): 
        """
        """

    def export_netcdf(self, where):
        """Function Docs 
        Parameters
        ----------
        Returns
        -------
        """
        pass
        


