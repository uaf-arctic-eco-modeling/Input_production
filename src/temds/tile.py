"""
Tile
----

Code for managing a single tile in the downscaling process

We use 'pixels' to mean grid cell item

tile.py is driven by a wrapper script/tool that creates a bunch of
datasource objects and then calls this methods to populate/run the tile object

"""
from pathlib import Path
import shutil

import xarray as xr
import pandas as pd
import yaml

import pyproj # For handling CRS in a variety of formats
from . import corrections 
from . import downscalers
from .datasources import annual, downscaled, crujra

from joblib import Parallel, delayed



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
        DataFrame with columns 'minx', 'miny', 'maxx', 'maxy', and a single row
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
            DataFrame with columns 'minx', 'miny', 'maxx', 'maxy', and a single
            row
        resolution: float
            resolution of pixels for tile
        crs: pyproj.crs.crs.CRS
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

        if (isinstance(extent, list) or isinstance (extent, tuple)) and len(extent) == 4:
            self.extent = pd.DataFrame([extent], columns=['minx', 'maxx', 'miny', 'maxy'])
        elif isinstance(extent, pd.DataFrame):
            self.extent = extent
        else:
            raise TypeError("extent must be either a pandas DataFrame or a list of 4 items [minx, miny, maxx, maxy]")

        self.resolution = resolution # Maybe? Maybe inherent from TIF? 
        self.buffer_area = buffer_px * self.resolution # maybe buffer_area is actually more of "buffer distance in projection units"
        self.buffer_pixels = buffer_px
        self.crs = crs

        self.verbose=False
        # A valid tile will be constructed when self.data has enough
        # information start implementing the stuff that is in downscaling.sh
        # however we end up re-naming the load/import functions here...

    @staticmethod
    def tile_from_manifest(in_file):
        """create a new empty tile from a manifest file
        
        Parameters
        ----------
        in_file: Path
            yml manifest file with 'index', 'extent', 'resolution', 'crs'
            and 'buffer_px'

        Returns
        -------
        Tile
        """
        with Path(in_file).open('r') as fd:
            manifest = yaml.load(fd, yaml.Loader)

        return Tile(
            manifest['index'],
            manifest['extent'],
            manifest['resolution'],
            manifest['crs'],
            buffer_px = manifest['buffer_px'],
        )

    @staticmethod
    def tile_from_directory(directory):
        """load tile from a directory with a manifest file
        
        Parameters
        ----------
        directory: Path
            must contain 'manifest.yml' with items needed by 
            `tile_from_manifest` and 'data

        Returns
        -------
        Tile
        """
        manifest = Path(directory).joinpath('manifest.yml')
        new = Tile.tile_from_manifest(manifest)
        new.load_from_directory(directory)
        return new

    
    def __repr__(self):
        """String Representation"""
        idx = str(self.index)
        data = ', '.join(self.data.keys())
        msg = f'Tile: {idx} with data for: {data}'
        return msg

    def toggle_verbose(self):
        """toggles verbose, and syncs with any items in data with `verbose`
        attribute
        """
        self.verbose = not self.verbose
        for item in self.data:
            if hasattr(self.data[item], 'verbose'):
                self.data[item].verbose = self.verbose


    def load_from_directory(self, directory):
        """
        Create in memory from a directory of file(s)
        """
        
        with Path(directory).joinpath('manifest.yml').open('r') as fd:
            manifest = yaml.load(fd, yaml.Loader)

        for item, _file in manifest['data'].items():
            in_path = Path(directory).joinpath(_file)
            if in_path.is_dir():
                self.data[item] = crujra.AnnualTimeSeries(
                    in_path, 
                    crs=self.crs, 
                    verbose=self.verbose
                )
            else:
                self.data[item] = xr.open_dataset(in_path, engine="netcdf4")

    def import_normalized(self, name, datasource, buffered=True, **kwargs):
        """Loads an item to `data` as name from datasource. Each datasource 
        (e.g. AnnualDaily, WorldClim) needs to implement a get_by_extent() 
        method that can return an xarray dataset or AnnualTimeseries to a 
        specified spatial temporal resolution and extent

        Parameters
        ----------
        name: str
            used as key for datasource in `data`
        datasource: Object
            Object must implement `get_by_extent` with 6 arguments
            (minx: float, maxx: float, miny: float, maxy: float, 
            extent_crs: pyproj.crs.crs.CRS, resolution: float)

        buffered: bool, Defaults True
            When true add buffer to tile data being clipped
        """
        minx, miny, maxx, maxy = self.extent[
            ['minx', 'miny', 'maxx', 'maxy']
        ].iloc[0]
        extent = minx, miny, maxx, maxy 
        if buffered:
            minx,maxx = minx-self.buffer_area,maxx+self.buffer_area
            miny,maxy = miny-self.buffer_area,maxy+self.buffer_area

        kwargs['resolution'] = self.resolution
        if self.verbose: 
            print(f'importing {name} from {datasource} for the extent: {extent}')
        self.data[name] = datasource.get_by_extent(
            minx, miny, maxx, maxy, self.crs, **kwargs
        ) 

    def save(self, where, **kwargs): 
        """Save `dataset` as a netCDF file.

        Parameters
        ----------
        where: str or Path
            Directory to save tile data to. A subdirectory Hxx_Vxx will be
            created if it does not exist.

        **kwargs
            fill_value: float, default 1.0e+20
            missing_value: float, default 1.0e+20
            use_zlib: bool, default True
            complevel: int, default 9
            overwrite: bool, default False
            items: list, default self.data.keys()
            update_manifest: bool, default False
            clear_existing: bool, default False
        """
        if isinstance(self.crs, str):
            crs = pyproj.crs.CRS.from_wkt(self.crs)
        elif isinstance(self.crs, pyproj.crs.crs.CRS):
            crs = self.crs.to_wkt()
        else:
            raise TypeError(
                f'CRS must be a string or pyproj.crs.crs.CRS, not {type(self.crs)}'
            )

        # Maybe better force to either WKT or pyproj.crs.crs.CRS object above?
        # Prevents having to do type checking later...

        minx, miny, maxx, maxy = self.extent[
            ['minx', 'miny', 'maxx', 'maxy']
        ].iloc[0]
        extent = minx, miny, maxx, maxy
        manifest = {
            'index': self.index,
            'extent': extent,
            'resolution': self.resolution,
            'crs': crs if isinstance(crs, str) else crs.to_wkt(),
            'buffer_px': self.buffer_pixels,
            'data': {}
        }

        lookup = lambda kw, ke, de: kw[ke] if ke in kw else de

        fill_value = lookup(kwargs, 'fill_value', 1.0e+20 )
        missing_value = lookup(kwargs, 'missing_value', 1.0e+20 )
        compress = lookup(kwargs, 'use_zlib', True)
        complevel = lookup(kwargs, 'complevel', 9)
        overwrite = lookup(kwargs, 'overwrite', False)
        to_save = lookup(kwargs, 'items', self.data.keys())
        update_manifest = lookup(kwargs, 'update_manifest', False)

        clear_existing = lookup(kwargs, 'clear_existing', False)

        climate_enc = {
                '_FillValue':fill_value, 
                'missing_value':missing_value, 
                'zlib': compress, 'complevel': complevel # USE COMPRESSION?
            }
        H, V = self.index
        root = Path(where).joinpath(f'H{H:02d}_V{V:02d}')
        if clear_existing and root.exists():
            shutil.rmtree(str(root))

            
        for name, ds in self.data.items():
            
            if name not in to_save:
                continue
            if self.verbose: print(f'Saving: {name}')
            
            if isinstance(ds, annual.AnnualTimeSeries):
                op = Path(where).joinpath(f'H{H:02d}_V{V:02d}', name) 
                op.mkdir(exist_ok=True, parents=True)
                for item in ds.data:
                    for _var in item.dataset.data_vars:
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
                manifest['data'][name] = str(name)
                continue



            out_file = Path(where).joinpath(f'H{H:02d}_V{V:02d}', f'{name}.nc') 
            out_file.parent.mkdir(exist_ok=True, parents=True)
            
            
            for _var in ds.data_vars:
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
                manifest['data'][name] = str( f'{name}.nc')
                
            else:
                raise FileExistsError('The file {out_file} exists and `overwrite` is False')
       
        manifest_file = Path(where).joinpath(f'H{H:02d}_V{V:02d}', 'manifest.yml')
        if manifest_file.exists() and update_manifest:
            with manifest_file.open('r') as fd:
                old = yaml.load(fd, yaml.Loader)
            man_data = old['data']
            man_data.update(manifest['data'])
            manifest['data'] = man_data
       
        with manifest_file.open('w') as fd:
            yaml.safe_dump(manifest, fd, sort_keys=False)

    def calculate_climate_baseline(self, start_year, end_year, target, source, **kwargs):
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
            start_year, end_year, **kwargs
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
        downscaled.attrs['data_year'] = year

        
        downscaled.rio.set_spatial_dims(x_dim="x", y_dim="y", inplace=True)
        downscaled.rio.write_crs(source.rio.crs, inplace=True)
        downscaled.rio.write_coordinate_system(inplace=True) 
        downscaled.rio.write_transform(source.rio.transform(), inplace=True)

        return downscaled


    def downscale_timeseries(self, downscaled_id, source_id, correction_id, variables, parallel=False):
        """
        Add downscaled to self.data dict as xarray dataset. 
        """

        if parallel:
            results = Parallel()(
                delayed(self.downscale_year)(year, source_id, correction_id, variables) for year in self.data[source_id].range()
            )
        else:
            results = []
            for year in self.data[source_id].range():
                if self.verbose: print(f'Downscaling {year}')
                data = self.downscale_year(year, source_id, correction_id, variables)
                results.append(
                    downscaled.AnnualDaily(year, data, crs=self.crs)
                )
        
        self.data[downscaled_id] = downscaled.AnnualTimeSeries(results)

    def to_TEM(self):
        '''
        [[ DRAFT ]]
        Convert downscaled data to a format suitable for TEM (Terrestrial Ecosystem Model).

        Returns the unbuffered tile data, as an xarray Dataset with variables renamed to match TEM expectations.
        '''
        ds_lst = []
        for year in self.data['downscaled_cru'].range():

            yr_data = self.data['downscaled_cru'][year].dataset

            ds = xr.Dataset()

            for v in ['tavg', 'vapo', 'nirr']:
                new_v = yr_data[v].resample(time='MS').mean()
                ds[v] = new_v

            for v in ['prec']:
                new_v = yr_data[v].resample(time='MS').sum()
                ds[v] = new_v

            ds = ds.rename_vars(name_dict={'tavg':'tair', 'vapo':'vapor_press', 'nirr':'nirr', 'prec':'precip'})
            ds_lst.append(ds)

        buffered_ds = xr.concat(ds_lst, dim='time')
        buffered_ds.attrs['data_years'] = f"{self.data['downscaled_cru'].range()}"
        buffered_ds.rio.set_spatial_dims(x_dim="x", y_dim="y", inplace=True)
        buffered_ds.rio.write_crs(self.crs, inplace=True)
        buffered_ds.rio.write_coordinate_system(inplace=True)

        mask_x = (buffered_ds.x >= self.extent['minx'].squeeze()) & (buffered_ds.x <= self.extent['maxx'].squeeze())
        mask_y = (buffered_ds.y >= self.extent['miny'].squeeze()) & (buffered_ds.y <= self.extent['maxy'].squeeze())

        unbuffered_ds = buffered_ds.where(mask_x & mask_y, drop=True)

        return unbuffered_ds
