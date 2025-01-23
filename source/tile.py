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
        self.data = {}# dictionary of normalized data, i.e:
                      # {
                      #     'crujra': xr.Dataset(...), 
                      #     'worldclim': xr.Dataset(...)
                      # }
        self.extent = None # aoi object, or a modified aoi object
        self.resolution # Maybe? Maybe inherent from TIF? 

        # A valid tile will be constructed when self.data has enough
        # informatiionto start implementing the stuff that is in downscaling.sh
        # however we end up re-naming the load/import functions here...


    def load_from_directory(self, directory):
        """
        Create in memory from a directory of file(s)
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


    def import_normalized(self, name, datasource):
        """
        each datasource (e.g. CRU_JRA_daily, WorldClim) needs to implement a 
        .get() method that can return an xarray dataset to a specified spatial 
        temporal rezolution and aoi extent

        tile.py is driven by a wrapper script/tool that creates a bunch of
          datasource objects and then calls this method to populate the tile object
        """
        
        self.data[name] = datasource.get(spatialrez=4, temporalrez='daily', aoi_extent=self.extent) 

    def save(self, where): 
        """
        Writes to disk. Result is a folder with various files in it.
        """

    def downscale(self, method='bilinear'):
        """
        Add downscaled to self.data dict as xarray dataset. 
        """
        pass

    def export_netcdf(self, where):
        """Function Docs 
        Parameters
        ----------
        Returns
        -------
        """
        pass
        


