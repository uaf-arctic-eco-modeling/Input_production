"""
Tile
----

Code for managing a single tile in the downscaling process

We use 'pixels' to mean grid cell item

tile.py is driven by a wrapper script/tool that creates a bunch of
datasource objects and then calls this methods to populate/run the tile object

"""

from pathlib import Path

import xarray as xr
import pandas as pd

from . import corrections 
from . import downscalers
from .crujra import AnnualTimeSeries


class Tile(object):
    """Object represents a "Tile" - a geographic area that can be
    downscaled. Downscaling refers to the process of taking coarse resolution
    data and creating finer resolution data. This is done by using an
    interpolation scheme as well as correction factors. The correction factors
    are typically derived from observed data and are used to adjust the data
    once it has been interpolated.


    Attributes
    ----------
    data: dict
        items must be xr.dataset or inherit from annual.AnnualTimeSeries keys
        should represent the data being stored, but can be anything
    index: tuple, or int
        the index (H,V) or N of the tile in the tile index primarily used for
        logging #TODO implement INT code
    extent: pandas.DataFrame
        DataFrame with columns 'minx','maxx','miny','maxy', and a single row
    resolution: float
        resolution of pixels for tile
    crs: ??
        CRS of tile. Items imported will be converted to this crs with pixel
        size of `resolution`
    buffer_px: int
        Number of pixels to buffer extent by in `crs`/`resolution`
    buffer_area: float
        area in `crs` units of pixel buffer

    """
    def __init__(self, index, extent, resolution, crs, buffer_px = 20):
        """

        Parameters
        ----------
        index: tuple, or int
            the index (H,V) or N of the tile in the tile index
            primarily used for logging
        extent: pandas.DataFrame
            DataFrame with columns 'minx','maxx','miny','maxy', and a single
            row
        resolution: float
            resolution of pixels for tile
        crs: ??
            CRS of tile. Items imported will be converted to this crs with
            pixel size of `resolution`
        buffer_px: int, Optional, Default = 20
            Number of pixels to buffer extent by in `crs`/`resolution`

        """
        self.data = {}# dictionary of normalized data, i.e:
                      # {
                      #     'daily_crujra': xr.Dataset(...), 
                      #     'monthly_worldclim': xr.Dataset(...)
                      # }
        self.index = index # 2 tuple (H, V)

        if isinstance(extent, list) and len(extent) == 4:
            self.extent = pd.DataFrame([extent], columns=['minx', 'maxx', 'miny', 'maxy'])
        elif isinstance(extent, pd.DataFrame):
            self.extent = extent
        else:
            raise TypeError("extent must be either a pandas DataFrame or a list of 4 items [minx, maxx, miny, maxy]")

        self.resolution = resolution # Maybe? Maybe inherent from TIF? 
        self.buffer_area = buffer_px * self.resolution
        self.buffer_pixels = buffer_px
        self.crs = crs


        # A valid tile will be constructed when self.data has enough
        # information start implementing the stuff that is in downscaling.sh
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
        """Loads an item to `data` as name from datasource. Each datasource 
        (e.g. AnnualDaily, WorldClim) needs to implement a get_by_extent() 
        method that can return an xarray dataset or AnnualTimeseries to a 
        specified spatial temporal resolution and extent

        Parameters
        ----------
        name: str
            used as key for datasource in `data`
        datasource: Object
            Object must implement `get_by_extent` with 6 arguments (minx: float,
            maxx: float, miny: float, maxy: float, crs:??, resolution: float)
        ) 
        buffered: bool, Defaults True
            When true add buffer to tile data being clipped
        """
        minx, maxx, miny, maxy = self.extent[
            ['minx','maxx','miny','maxy']
        ].iloc[0]
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
                op = Path(where).joinpath(f'H{H:02d}_V{V:02d}', name) 
                op.mkdir(exist_ok=True, parents=True)
                for item in ds.data:
                    for _var in item.dataset.data_vars:
                        print(_var)
                        item.dataset[_var].rio.update_encoding(climate_enc, inplace=True)
                    out_file = Path(op).joinpath(f'{name}-{item.year}.nc') 
                    if  not out_file.exists() or overwrite:
                        if overwrite and out_file.exists():
                            out_file.unlink()
                        item.dataset.attrs['data_year'] = item.year    
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

    def calculate_climate_baseline(self, start_year, end_year, target, source):
        """Calculate the climate baseline for the tile from data in an 
        AnnulTimeseries object

        Parameters
        ----------
        start_year: int
            Inclusive start year for baseline
        end_year: int
            Inclusive end year for baseline
        target: str
            name to set baseline data to in `data`
        source: str
            An AnnualTimeseries item in `data` with 
            `create_climate_baseline(start_year, end_year)` method
        """

        self.data[target] = self.data[source].create_climate_baseline(
            start_year, end_year
        )

    def calculate_correction_factors(
            self, baseline_id, reference_id, variables, 
            factor_id='correction_factors'
        ):
        """
        Calculate correction factors based on baseline and reference datasets.

        This method computes correction factors for specified variables by
        applying user-defined functions to the baseline and reference datasets.
        The resulting correction factors are stored in the `self.data`
        dictionary under the specified `factor_id`.

        Parameters
        ----------
        baseline_id : str
            The key to access the baseline dataset in `self.data`.
        reference_id : str
            The key to access the reference dataset in `self.data`.
        variables : dict
            A dictionary where keys are variable names and values are
            dictionaries containing the following keys:
                - 'function' (str): The name of the function to apply, which
                  must exist in `corrections.LOOKUP`. 
                - 'name' (str): The name to assign to the resulting correction 
                  factor.
                - factor_id : str, optional. The key under which the resulting 
                  correction factors will be stored in `self.data`. Defaults to
                  'correction_factors'.

        Raises
        ------
        KeyError
            If `baseline_id` or `reference_id` is not found in `self.data`.
        KeyError
            If the specified function is not found in `corrections.LOOKUP`.

        Returns
        -------
        None
            The correction factors are stored in `self.data[factor_id]`.
        """
        reference = self.data[reference_id]
        baseline = self.data[baseline_id]
        temp = []


        for var, info in variables.items():
            func = corrections.LOOKUP[info['function']]
            current = func(baseline, reference, info)
            current.name = info['name']
            temp.append(current)
           

        correction_factors = xr.merge(temp)
        self.data[factor_id] = correction_factors

    def downscale_year(self, year, source_id, correction_id, variables):
        """Downscale a singe year of `data[source_id]` using corrections
        in `data['correction_id]`, and configuration in variables


        Variables example: 
        variables = {
            'tmax': {
                'function': 'temperature', 
                'temperature': 'tmax',
                'correction_factor':'tmax', 
                'name': 'tmax'
            },
            'prec': {
                'function': 'precipitation', 
                'precipitation': 'pre',
                'correction_factor':'prec', 
                'name': 'prec'
            },
        }

        Parameters
        ----------
        year: int
            the year to downscale
        source_id: str
            AnnualTimeseries item in `data`
        correction_id: str
            xr.dataset item in `data`
        variables: dict
            dictionary mapping variable names to variable configurations
            each key 'var' has and dictionary item with... 
            see example above
        
        Returns
        -------
        xr.dataset
            a single downscaled year

        """
        correction = self.data[correction_id]
        source = self.data[source_id][year].dataset
        temp = []
        for var, info in variables.items():
            func = downscalers.LOOKUP[info['function']]
            current = func(source, correction, info)
            current.name = info['name']
            temp.append(current)
        
        downscaled = xr.merge(temp)
        return downscaled


    def downscale_timeseries(self, downscaled_id, source_id, correction_id, variables):
        """
        Add downscaled to self.data dict as xarray dataset. 
        """
        results = []
        for item in self.data[source_id]:
            year = item.year
            results.append(
                self.downscale_year(year, source_id, correction_id, variables)
            )
        
        self.data[downscaled_id] = downscaled.AnnualTimeSeries(results)

