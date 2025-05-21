"""
WorldClim
---------

Data structures representing WorldClim data

"""
from pathlib import Path
import gc
import shutil
import copy


from affine import Affine
import xarray as xr
import rioxarray  # activate 
import numpy as np
from osgeo import gdal

from temds.remote_zip import RemoteZip
from temds.constants import MONTH_START_DAYS 
from temds import climate_variables
from .base import TEMDataSet



gdal.UseExceptions() ## gdal 4.0 future proofing


## REGISTER CLIMATE VARIABLES
climate_variables.register('tair', 'worldclim', 'tavg')
climate_variables.register('tmin', 'worldclim', 'tmin')
climate_variables.register('tmax', 'worldclim', 'tmax')
climate_variables.register('prec', 'worldclim', 'prec')
climate_variables.register('nirr', 'worldclim', 'srad')
climate_variables.register('wind', 'worldclim', 'wind')
climate_variables.register('vapo', 'worldclim', 'vapr')

WORLDCLIM_VARS = climate_variables.aliases_for('worldclim')

WORLDCLIM_NAMING_CONVENTION = 'wc2.1_30s_{var}'

WORLDCLIM_2_1_URL_PATTERN = f'https://geodata.ucdavis.edu/climate/worldclim/2_1/base/{WORLDCLIM_NAMING_CONVENTION}.zip'
WORLDCLIM_URL_PATTERN = WORLDCLIM_2_1_URL_PATTERN

class WorldClim(TEMDataSet):
    """WorldClim data is monthly data that represents long term normal 
    climate conditions.

    attributes
    ----------
    dataset: xr.Dataset
        Contains a DataArray for each var in `vars` with a time step for
        each month in `months`
    vars: list
        list of objects climate variables
    verbose: bool
        verbosity flag
    months: list like
        list of months represented by dataset
        should contain only values from 1 to 12, non-repeating
    """
    def __init__ (self, 
            data_input,
            extent_raster = None, verbose=False, 
            _vars=WORLDCLIM_VARS, months=range(1,13), 
            **kwargs
        ):
        """
        Parameters
        ----------
        data_input: path, or str
            When given an existing file (.nc), the file is loaded via `load`.
            When given a str starting with http and ending in .zip, and if
            `extent_raster` is not None, dataset is created based on
            `extent_raster` and populated from remote data.
        extent_raster : path, optional
            Path to raster to pull extent and resolution from if not provided
            extent and resolution are pulled from first raster open
        verbose: bool, default False
            see `verbose`
        _vars: list, default CRU_JRA_VARS
            see `vars`
        months: list like
            list of months, represented as numbers, to use. Useful for testing
            Values in list are from 1 to 12 for January through december.
            Default list includes all months.
        **kwargs: dict
            'local_location': local working path or options to forward to the
            `load_from_*` functions.
            
        
        Attributes
        ----------
        self.dataset: xarray.dataset 
            Daily CRU JRA data for a year
        self.verbose: bool
            when true status messages are enabled
        self.vars: list
            list of climate variables to load, defaults all(CRU_JRA_VARS)
        self.months: list,
            list of numbers containing months represented in dataset 1 to 12 

        Raises
        ------
        IOError
            When file/files to load is wrong format or do not exist

        """
        self.dataset = None ## xarray data 
        self.verbose = verbose 
        self.vars = _vars
        self.months = list(months)
        
        kwargs['local_location'] = kwargs['local_location'] \
                            if 'local_location' in kwargs else './_worldclim_'
        
        url = str(data_input)
        data_input = Path(data_input)
        if data_input.exists() and data_input.suffix == '.nc':
            self.load(data_input)
        elif url[:4] == 'http' and url[-4:] == '.zip' and not extent_raster is None:
            ll = kwargs['local_location']
            del(kwargs['local_location'])
            self.load_from_web(
                ll, extent_raster, 
                cleanup_uncompressed=True, url_pattern=url,
                **kwargs
            )
        elif data_input.exists() and data_input.is_dir() and not extent_raster is None:
            self.load_from_directory(
                data_input, extent_raster, 
                cleanup_uncompressed=True, 
                resample_alg='bilinear', no_data=-3.4e+38
            )
        ## elif...
        ## OTHER options could be implemented here. to load already downloaded
        ## data or whatever.
        else:
            if self.verbose: print('Data not initialized')
            # raise IOError('No data_inputs found')
    
    def new_from_raster_extent(self, raster, buffer_px=30):
        """Creates new xr.dataset for `self.dataset` using 
        the extent, transform, and projection of `raster`. Also includes a
        buffer, which ends up being helpful in downstream operations.
        `self.dataset` resolution and extent are calculated from `rasters`
        transform.

        Parameters
        ----------
        raster: path
            path to a raster file that can be opened as a gdal dataset
        """

        extent_ds = gdal.Open(raster)
        gt = extent_ds.GetGeoTransform()
        minx = gt[0] - (buffer_px * extent_ds.RasterXSize)
        miny = gt[3] - (buffer_px * extent_ds.RasterYSize)
        maxx = minx + gt[1] * extent_ds.RasterXSize + (buffer_px * extent_ds.RasterXSize)
        maxy = miny + gt[5] * extent_ds.RasterYSize + (buffer_px * extent_ds.RasterYSize)
        
        extent = (minx, miny, maxx, maxy) #_warp_order
        if self.verbose: print(f'extent {extent}')
        if self.verbose: print(f'extents includes buffer of {buffer_px} pixels')
        x_res, y_res = gt[1], gt[5]
        if self.verbose: print(f'resolution, {x_res},{y_res}')

        out_x_size = extent_ds.RasterXSize
        out_y_size = extent_ds.RasterYSize
        if self.verbose: print (f'out size {out_x_size}, {out_y_size}')

        
        lat_dim = np.arange( miny, maxy, abs(y_res) ) + (abs(y_res)/2)

        # lat_dim is empty if this is true, so swap min and max and redo
        if maxy < miny: 
            miny, maxy = maxy, miny
            lat_dim = np.arange(miny,maxy, abs(y_res)) + (abs(y_res)/2)
            miny, maxy = maxy, miny ## keep for gdal

        ## do we need the dimension trick here?
        lon_dim = np.arange(minx,maxx, abs(x_res)) + (abs(x_res)/2)


        rows = len(lat_dim)
        cols = len(lon_dim)

        dims = ['time', 'lat', 'lon']
        n_months = len(self.months)
        shape = [n_months, rows, cols]
        empty_data = np.zeros(n_months * rows * cols)\
                       .reshape(shape).astype('float32')
        data_vars = { 
            var : (dims, copy.deepcopy(empty_data) ) for var in self.vars
        }

        doy = [MONTH_START_DAYS[mn-1] for mn in self.months]
        coords={
            'lat': lat_dim, 
            'lon': lon_dim,
            'time': doy
        }

        self.dataset = xr.Dataset(data_vars=data_vars, coords=coords)
        self.dataset.rio.write_crs(extent_ds.GetProjection(),inplace=True)\
            .rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)\
            .rio.write_coordinate_system(inplace=True) 

        # from_gdal very important here.
        self.dataset.rio.write_transform(Affine.from_gdal(*gt), inplace=True)

        ## I don't know why but I have to do this twice. It's not the inplace
        ## not working and needing the assignment, I tried both ways in the 
        ## first call above and it didn't make a difference. 
        self.dataset = self.dataset\
            .rio.write_crs(self.dataset.rio.crs.to_wkt(), inplace=True)\
            .rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)\
            .rio.write_coordinate_system(inplace=True)

    def set_var_from_web(
            self, var, url, local_location, 
            file_format=None, resample_alg='bilinear', cleanup=True, 
            overwrite=False,
            **kwargs
        ):
        """Download and set climate data from web based zip file.

        Parameters
        ----------
        var: str
            one of the climate variables from  `WORLDCLIM_VARS` and 
            `self.vars` 
        url: str
            url of a remote zip file containing .tif files for each month 
            of the year
        local_location: path
            path where local data is stored/processed
        file_format: str, optional
            format string for files with formating directiions for `var`(str) 
            and `mn`(int). I.E '{var}/wc2.1_30s_{var}_{mn:02d}.tif'
        resample_alg: str, default 'bilinear'
            gdal.warp resampling algorithm 
        cleanup: bool, default True
            when true clean up temporary unziped data
        **kwargs: dict
            arguments passed to non-default parameters of `set_var_from_zip`
        """
        ## download with complete url so we need complete local location
        results = self.download(
            url, local_location, 
            vars=None, overwrite=overwrite
        )
        archive = results['download']

        # archive = RemoteZip(url, self.verbose)
        # overwrite = True
        # archive.download(local_location, overwrite)

        self.set_var_from_zip(
            var, archive, local_location, file_format=file_format, 
            resample_alg=resample_alg, cleanup=cleanup, **kwargs
        )
        # in_dir = Path(archive.unzip(f'{local_location}/{var}'))
        # self.set_var_from_dir(var, local_location, file_format, resample_alg=resample_alg, **kwargs)

        # if cleanup:
        #     shutil.rmtree(in_dir)

    def set_var_from_zip(
            self, var, archive, local_location, file_format=None, 
            resample_alg='bilinear', cleanup=True, **kwargs
        ):
        """
        set climate data from zip file.

        Parameters
        ----------
        var: str
            one of the climate variables from  `WORLDCLIM_VARS` and 
            `self.vars` 
        archive: path
            zip file containing .tif files for each month of the year
        local_location: path
            path where local data is stored/processed
        file_format: str, optional
            format string for files with formating directiions for `var`(str) 
            and `mn`(int). I.E '{var}/wc2.1_30s_{var}_{mn:02d}.tif'
        resample_alg: str, default 'bilinear'
            gdal.warp resampling algorithm 
        cleanup: bool, default True
            when true clean up temporary unziped data
        **kwargs: dict
            arguments passed to non-default parameters of `set_var_from_dir`
        """
        if type(archive) is str:
            ## we can cheat and reuse this code if we manually set 
            # archive.local_file
            temp = RemoteZip('', self.verbose)
            temp.local_file=archive
            archive = temp
        in_dir = Path(archive.unzip(f'{local_location}/{var}'))
        self.set_var_from_dir(
            var, local_location, file_format, 
            resample_alg=resample_alg, **kwargs
        )

        if cleanup:
            shutil.rmtree(in_dir)

    def set_var_from_dir(self, var, in_dir, file_format=None, **kwargs):
        """
        set climate data from directory.

        Parameters
        ----------
        var: str
            one of the climate variables from  `WORLDCLIM_VARS` and 
            `self.vars` 
        in_dir: path
            directory containing .tif files for each month of the year
            matching `file_format`
        local_location: path
            path where local data is stored/processed
        file_format: str, optional
            format string for files with formatting directives for `var`(str) 
            and `mn`(int). I.E '{var}/wc2.1_30s_{var}_{mn:02d}.tif'
        resample_alg: str, default 'bilinear'
            gdal.warp resampling algorithm 
        **kwargs: dict
            arguments passed to non-default parameters of `set_from_raster`
        """
        if self.verbose: print(f"setting {var} from raw data at '{in_dir}'")
        
        if file_format is None:
            file_format = '{var}/wc2.1_30s_{var}_{mn:02d}.tif'

        for month in self.months:
            data_raster = Path(in_dir, file_format.format(var=var, mn=month))
            self.set_from_raster(
                var, month-1, data_raster, **kwargs
            )

    def set_from_raster(self,
            var, idx, data_raster, 
            resample_alg='bilinear', no_data=-3.4e+38,
            initialize_if_needed=True,
        ):
        """
        sets a variable a a timestep index in `self.dataset`

        Parameters
        ----------
        var: str
            one of the climate variables from  `WORLDCLIM_VARS` and 
            `self.vars` 
        idx: int
            integer  based time step index to `self.dataset`
        data_raster: path
            path to tiff file
        resample_alg: str, default 'bilinear'
            gdal.warp resampling algorithm 
        no_data: float
            Not implemented 
        """
        
        if self.verbose: 
            print(f'loading {var} data from {data_raster} at index {idx}')
        if self.dataset is None:
            
            if not initialize_if_needed:
                print(f'data not initialized.')
                raise TypeError('NEEDS AN ERROR')
            if self.verbose: 
                print(
                    f'data not initialized. '
                    'Initializing with extent from {data_raster}'
                )
            self.new_from_raster_extent(data_raster)

        gt = self.dataset.rio.transform().to_gdal()

        minx = gt[0]
        miny = gt[3]
        maxx = minx + abs(gt[1]) * self.dataset.lon.size
        maxy = miny + abs(gt[5]) * self.dataset.lat.size
        extent = (minx, miny, maxx, maxy) #_warp_order
        if self.verbose: print(f'.. Running gdal.Warp to extent {extent}')

        # load result to memory so we don't have temp files
        result = gdal.Warp(
            '', data_raster, 
            xRes=abs(gt[1]), yRes=abs(gt[5]),
            outputBounds=extent,
            dstSRS=self.dataset.rio.crs.to_wkt(),
            format='mem',
            resampleAlg=resample_alg,
            dstNodata=-3.4e+38,
            outputType=gdal.GDT_Float32,
            # srcBands = [1],
            # dstBands = [1]
        )
        pixels = result.ReadAsArray()
        if gt[5] < 0: # filp flop if res_y is negative
            pixels = pixels[::-1]
            
        pixels[pixels <= -3e30] = np.nan # fix
        
        self.dataset[var][idx] = pixels # 0based index
        [gc.collect(i) for i in range(2)]

    def load(self, in_path):
        """loads monthly climate normals. Assumes file contains 
        all required variables, correct extent and time steps.

        Parameters
        ----------
        in_path: Path
            path to nc file
        """
        if self.verbose: 
            print(f"...loading file '{in_path}' ...assuming correct time step and "
                  "region are set"
            )
        # self.dataset = rioxarray.open_rasterio(in_path, engine="netcdf4")
        self.dataset = xr.open_dataset(in_path, engine="netcdf4")
        crs = self.dataset.spatial_ref.attrs['spatial_ref']
        gt = (float(f) for f in self.dataset.spatial_ref.attrs['GeoTransform'].split(' '))

        
        self.dataset.rio.write_crs(crs,inplace=True)\
            .rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=True)\
            .rio.write_coordinate_system(inplace=True) 
        
        # from_gdal very important here.
        self.dataset.rio.write_transform(Affine.from_gdal(*gt), inplace=True)
        if self.verbose: print('dataset initialized')

    def load_from_web(
            self, local_location, extent_raster=None, 
            cleanup_uncompressed=True, url_pattern=None,
            resample_alg='bilinear', no_data=-3.4e+38
        ):
        """Create `self.dateset` from extent raster and load from web source

        Parameters
        ----------
        local_location: path
            local data and working directory
        extent_raster: path
            Path to raster to pull extent and resolution from
            if not provided  extent and resolution are 
            pulled from first raster open
        cleanup_uncompressed: bool, Default True,
        url_pattern: Str, default `WORLDCLIM_URL_PATTERN`
            Url pattern containing {var} formatter
        resample_alg: str, default 'bilinear'
            gdal.warp resampling algorithm 
        no_data: float
            Not implemented 

        """

        if url_pattern is None:
            url_pattern = WORLDCLIM_URL_PATTERN
        if extent_raster:
            self.new_from_raster_extent(extent_raster)
        for var in self.vars:
            self.set_var_from_web(
                var, url_pattern.format(var=var), local_location,
                cleanup=cleanup_uncompressed, 
                resample_alg=resample_alg, no_data=no_data
            )

    def load_from_directory(
            self, local_location, extent_raster=None, 
            cleanup_uncompressed=True, url_pattern=None,
            resample_alg='bilinear', no_data=-3.4e+38
        ):
        """Create `self.dateset` from extent raster and load from web source

        Parameters
        ----------
        local_location: path
            local data and working directory
        extent_raster: path
            Path to raster to pull extent and resolution from
            if not provided  extent and resolution are 
            pulled from first raster open
        cleanup_uncompressed: bool, Default True,
        url_pattern: Str, default `WORLDCLIM_URL_PATTERN`
            Url pattern containing {var} formatter
        resample_alg: str, default 'bilinear'
            gdal.warp resampling algorithm 
        no_data: float
            Not implemented 

        """

        if url_pattern is None:
            url_pattern = WORLDCLIM_URL_PATTERN
        if extent_raster:
            self.new_from_raster_extent(extent_raster)
        for var in self.vars:

            
            if Path(f'{local_location}/{var}').exists():
                self.set_var_from_dir(
                    var, 
                    local_location, 
                    resample_alg=resample_alg, 
                    no_data=no_data
                )
            
            else:
                var_dir = WORLDCLIM_NAMING_CONVENTION.format(var=var)
                archive = f'{local_location}/{var_dir}.zip'
                self.set_var_from_zip(
                    var, 
                    archive, 
                    local_location, 
                    cleanup=cleanup_uncompressed, 
                    resample_alg=resample_alg, 
                    no_data=no_data
                )
        
            # self.set_var_from_web(
            #     var, url_pattern.format(var=var), local_location,
            #     cleanup=cleanup_uncompressed, 
            #     resample_alg=resample_alg, no_data=no_data
            # )

    def download(self, url_pattern, local_location, vars='all', overwrite=False):
        """Download data, assumes remote data is in .zip format

        Parameters
        ----------
        url_pattern: str
            a url that may contain '{var}' formatter.
        local_location: Path
            path to save data to. When `vars` is str or list
            data for each variable is saved in a subdirectory named
            as the variable. When `vars` is None data is save 
            directly to `local_location`
        vars: str, list, or None:
            if str and vars=='all'
                vars is set to all vars in self.vars
            if str and vars!='all'
                vars must be in `WORLDCLIM_VARS`
            if list
                each item must be in
            if None:
                assumes URL is a complete url with no {var} formatter

        Returns
        -------
        dict:
            dictionary of RemoteZip objects for var in `vars` with 
            self.local_file set. if vars is one only key in dict is 'download'
        """
        if self.verbose: print('..WorldClim.download', local_location)
        if vars == 'all':
            vars = self.vars
        if vars is None and url_pattern.format(vars) != url_pattern:
            raise TypeError('URL is a formatter and no var is provided')
        if not type(vars) is list:
            vars = [vars]
        completed = {}
        for var in vars:
            
            url =  url_pattern.format(var=var)
            archive = RemoteZip(url, self.verbose)
            archive.download(local_location, overwrite)
            key = var
            if key is None:
                key = 'download'
            completed[key] = archive
        return completed

    # def save(self, out_file, missing_value=1.e+20, fill_value=1.e+20, overwrite=False):
    #     """Save `dataset` as a netCDF file.

    #     Parameters
    #     ----------
    #     out_file: path
    #         file to save
    #     missing_value: float, default 1.e+20
    #     fill_value: float, default 1.e+20
    #         values set as _FillValuem, and missing_value in netCDF variable
    #         headers
    #     """
    #     climate_enc = {
    #         '_FillValue':fill_value, 
    #         'missing_value':missing_value, 
    #         'zlib': True, 'complevel': 9 # USE COMPRESSION?
    #     }
        
    #     for _var in self.vars:
    #         self.dataset[_var].rio.update_encoding(climate_enc, inplace=True)
            
    #     if  not out_file.exists() or overwrite:
    #         self.dataset.to_netcdf(
    #                 out_file, 
    #                 # encoding=encoding, 
    #                 engine="netcdf4",
    #                 # unlimited_dims={'time':True}
    #             )
    #     else:
    #         raise FileExistsError('The file {out_file} exists and `overwrite` is False')
        
    # def get_by_extent(self, minx, maxx, miny, maxy, extent_crs, resolution = None):
    #     """Returns xr.dataset for use in downscaling

    #     Parameters
    #     ----------
    #     minx: Float
    #         Minimum x coord, in `self.dataset` projection
    #     maxx: Float
    #         Maximum x coord, in `self.dataset` projection
    #     miny: Float
    #         Minimum y coord, in `self.dataset` projection
    #     maxy: Float
    #         Maximum y coord, in `self.dataset` projection
    #     resolution: float, Optional
    #         Resolution of dataset to return, If None, The resolution is
    #         not changed from `self.dataset`

    #     Returns
    #     -------
    #     xarrray.Dataset
    #         subset of data from extent (`minx`,`miny`)(`maxx`,`maxy`) and 
    #         at `resolution`

    #     """
    #     if extent_crs != self.dataset.rio.crs:
    #         local_dataset = self.dataset.rio.reproject(extent_crs)
    #     else:
    #         local_dataset = self.dataset

    #     # return clip_xr_dataset(self.dataset,minx, maxx, miny, maxy, resolution )
    #     if minx>maxx:
    #         print('swap x')
    #         minx, maxx = maxx,minx
    #     if miny>maxy:
    #         print('swap y')
    #         miny, maxy = maxy,miny  
                
            
    #     mask_x =  ( local_dataset.lon >= minx ) & ( local_dataset.lon <= maxx )
    #     mask_y =  ( local_dataset.lat >= miny ) & ( local_dataset.lat <= maxy )
    #     tile = local_dataset.where(mask_x&mask_y, drop=True)

    #     tile.rio.write_crs(local_dataset.rio.crs, inplace=True)
    #     return tile