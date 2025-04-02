"""
Tile
----



"""
from pathlib import Path
from .crujra import AnnualTimeSeries


class Tile(object):
    """
    """
    def __init__(self, index, extent, resolution, crs, buffer_px = 20):
        """
        """
        self.data = {}# dictionary of normalized data, i.e:
                      # {
                      #     'daily_crujra': xr.Dataset(...), 
                      #     'monthly_worldclim': xr.Dataset(...)
                      # }
        self.index = index # 2 tuple (H, V)
        self.extent = extent #Dataframe with 'minx','maxx','miny','maxy'
        self.resolution = resolution # Maybe? Maybe inherent from TIF? 
        self.buffer_area = buffer_px * self.resolution
        self.buffer_pixels = buffer_px
        self.crs = crs



        # A valid tile will be constructed when self.data has enough
        # informatiionto start implementing the stuff that is in downscaling.sh
        # however we end up re-naming the load/import functions here...


    def load_from_directory(self, directory):
        """
        Create in memory from a directory of file(s)
        """
        pass

    # def load_extent(self, extent_file):
    #     """
    #     """
    #     pass

    def load_data(self, data): #or (self, name, data)? or all?
        """
        """
        pass


    def import_normalized(self, name, datasource, buffered=True):
        """
        each datasource (e.g. CRU_JRA_daily, WorldClim) needs to implement a 
        .get() method that can return an xarray dataset to a specified spatial 
        temporal resolution and aoi extent

        tile.py is driven by a wrapper script/tool that creates a bunch of
          datasource objects and then calls this method to populate the tile object
        """
        minx, maxx, miny, maxy = self.extent[['minx','maxx','miny','maxy']].iloc[0]
        if buffered:
            minx,maxx = minx-self.buffer_area,maxx+self.buffer_area
            miny,maxy = miny-self.buffer_area,maxy+self.buffer_area
        self.data[name] = datasource.get_by_extent(
            minx, maxx, miny, maxy, self.crs, self.resolution
        ) 

    def save(self, where, missing_value=1.e+20, fill_value=1.e+20, overwrite=False):
        """Save `dataset` as a netCDF file.

        Parameters
        ----------
        out_file: path
            file to save
        missing_value: float, default 1.e+20
        fill_value: float, default 1.e+20
            values set as _FillValuem, and missing_value in netCDF variable
            headers
        """
        climate_enc = {
                '_FillValue':fill_value, 
                'missing_value':missing_value, 
                'zlib': True, 'complevel': 9 # USE COMPRESSION?
            }
        for name, ds in self.data.items():
            
            H, V = self.index
            if type(ds) is AnnualTimeSeries:
                op = Path(where).joinpath(f'H{H:02d}_V{V:02d}','crujra') 
                op.mkdir(exist_ok=True, parents=True)
                for item in ds.data:
                    for _var in item.dataset.data_vars:
                        print(_var)
                        item.dataset[_var].rio.update_encoding(climate_enc, inplace=True)
                    out_file = Path(op).joinpath(f'crujra-{item.year}.nc') 
                    if  not out_file.exists() or overwrite:
                        if overwrite and out_file.exists():
                            out_file.unlink()
                        item.dataset.to_netcdf(
                            out_file, 
                            # encoding=encoding, 
                            # mode='w',
                            engine="netcdf4",
                            # unlimited_dims={'time':True}
                        )
                    else:
                        raise FileExistsError('The file {out_file} exists and `overwrite` is False')

                # ds.save( ## why does this not work?? 
                #     op, 'crujra-{year}.nc', 
                #     missing_value, fill_value, overwrite
                # )

                continue



            out_file = Path(where).joinpath(f'H{H:02d}_V{V:02d}', f'{name}.nc') 
            out_file.parent.mkdir(exist_ok=True, parents=True)
            
            
            for _var in ds.data_vars:
                print(_var)
                ds[_var].rio.update_encoding(climate_enc, inplace=True)
                # try: del ds[_var].attrs['_FillValue']
                # except: pass
                
            if  not out_file.exists() or overwrite:
                if overwrite and out_file.exists():
                    out_file.unlink()
                    
                ds.to_netcdf(
                        out_file, 
                        # encoding=encoding, 
                        # mode='w',
                        engine="netcdf4",
                        # unlimited_dims={'time':True}
                    )
                
            else:
                raise FileExistsError('The file {out_file} exists and `overwrite` is False')

    def calcualte_cru_longterm_average(self, start_year, end_year, key='cru_AnnualTimeSeries'):

        self.data['cru_avg'] = self.data[key].create_climate_average(start_year, end_year)


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
        


