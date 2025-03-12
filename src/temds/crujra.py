"""
CRU JRA
-------

Data structures representing CRU JRA data
"""
import datetime
import xarray as xr
import os
import gzip
import shutil
from pathlib import Path

from .clip_xarray import clip_xr_dataset


CRU_JRA_VARS = (
    'tmin','tmax','tmp','pre',
    'dswrf','ugrd','vgrd','spfh','pres'
)

CRU_JRA_RESAMPLE_LOOKUP = {
    'tmin': 'mean',
    'tmax': 'mean',
    'tmp': 'mean',
    'pre': 'sum',  # Might have issue here with summing nans --> leads to 0, should be nan
                   # hopefully fixed by pinning xarray version to one that leads to nans.
    'dswrf': 'sum',
    'ugrd': 'mean',
    'vgrd': 'mean',
    'spfh': 'mean',
    'pres': 'mean',
    
}

CRU_JRA_RESAMPLE_METHODS  = {
    'mean': lambda x: x.resample(time='1D').mean(),
    'sum':  lambda x: x.resample(time='1D').sum(),
}

class CRU_JRA_daily(object):
    """CUR JRA resampled data daily for a year, This class 
    assumes data for a single year in input file
    """
    def __init__ (self, year, in_path,verbose=False, _vars=CRU_JRA_VARS,  **kwargs):
        """
        Parameters
        ----------
        year: int
            year represented by data
        in_path: path
            When given an existing file (.nc), the file is loaded via `load`.
            or
            When given an existing directly, raw data is loaded via 
            `load_from_raw`. Also provide **kwargs as needed to use as optional
            arguments in `load_from_raw`
        verbose: bool, default False
            see `verbose`
        _vars: list, default CRU_JRA_VARS
            see `vars`
        **kwargs: dict
            arguments passed to non-default parameters of `load_from_raw` 
            if `in_path` is a directory.
        
        Attributes
        ----------
        self.year: int 
            year of data being represented.
        self.dataset: xarray.dataset 
            Daily CRU JRA data for a year
        self.verbose: bool
            when true status messages are enabled
        self.vars: list
            list of climate variables to load, defaults all(CRU_JRA_VARS)

        Raises
        ------
        IOError
            When file/files to load is wrong format or do not exist

        """
        self.year = year
        self.dataset = None ## xarray data 
        self.verbose = verbose 
        self.vars = _vars

        in_path = Path(in_path)
        if in_path.exists() and in_path.suffix == '.nc':
            self.load(in_path)
        elif in_path.exists() and in_path.is_dir(): 
            self.load_from_raw(in_path, **kwargs)
        else:
            raise IOError('No Inputs found')

        

    def load_from_raw(
            self, data_path, aoi_extent=None, file_format = None, 
            cleanup_uncompressed=True
        ):
        """Loads raw (direct from source) CRU JRA files, resamples to a daily
        timestep, and clips to an extent if provided

        Parameters
        ----------
        data_path: path
            a directory containing raw cru jra files to be loaded by matching
            file_format. 
        aoi_extent: tuple, optional
            clipping extent(minx, maxx, miny, maxy) geo-coordinates in 
            degrees(WGS84) # is this really the order we want?
        file_format: str, defaults None
            string that contains {var} and {yr} formatters to match. When 
            None is passed, '{var}/crujra.v2.5.5d.{var}.{yr}.365d.noc.nc.gz' 
            pattern is used; this format matches CUR JRA file format conventions
            where each variable is nested in a {var} subdirectory at the root 
            `data_path`
        cleanup_uncompressed: bool, default True
            if true uncompressed raw data is deleted when loading is complete
        """
        if self.verbose: print(f"Loading from raw data at '{data_path}'")

        if file_format is None:
            file_format = '{var}/crujra.v2.5.5d.{var}.{yr}.365d.noc.nc.gz'


        local_dataset = None
        for var in self.vars:
            _path = os.path.join(
                data_path, 
                file_format.format(var=var, yr=self.year)
            )
            if self.verbose: 
                print(f"..loading raw data for '{var}' from '{_path}'")

            cleanup = False
            if _path[-3:] == '.gz':
                with gzip.open(_path, 'rb') as f_in:
                    with open(_path[:-3], 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                _path = _path[:-3]
                # this ensures cleanup only occurs on files we uncompress
                # and not already uncompressed files the user may still need
                if cleanup_uncompressed:
                    cleanup = True

            temp = xr.open_dataset(_path, engine="netcdf4")
            
            if aoi_extent is not None:
                if self.verbose: print('..clipping to aoi')
                mask_x =  ( temp.lon >= aoi_extent[0] ) \
                        & ( temp.lon <= aoi_extent[1] )
                mask_y =  ( temp.lat >= aoi_extent[2] ) \
                        & ( temp.lat <= aoi_extent[3] )
                temp = temp.where(mask_x & mask_y, drop=True)


            method = CRU_JRA_RESAMPLE_LOOKUP[var]
            temp = CRU_JRA_RESAMPLE_METHODS[method] (temp)
                                # yr_data['tmax'].resample(time='1D').mean()
           
            if local_dataset is None:
                local_dataset = temp
            else:
                local_dataset = local_dataset.assign({var:temp[var]})

            if cleanup:
                os.remove(_path)  

        ## this is to set the attribute at the right level in the dataset
        for var in self.vars:
            temp = local_dataset[var]
            method = CRU_JRA_RESAMPLE_LOOKUP[var]
            temp = temp.assign_attrs( {'cell_methods':f'time:{method}'} )
            local_dataset = local_dataset.assign({var:temp})
            

        
        self.dataset = local_dataset
        if self.verbose: 
            print('..All raw data successfully loaded clipped and resampled.')
            print('dataset initialized')
        

    def load(self, in_path):
        """Load daily data from a single file. Assumes file contains 
        all required variables, correct extent and daily timestep
        """
        if self.verbose: 
            print(f"loading file '{in_path}' assuming correct timestemp and "
                  "region are set"
            )
        self.dataset = xr.open_dataset(in_path, engine="netcdf4")
        if self.verbose: print('dataset initialized')
    
    def save(self, out_file, missing_value=1.e+20, fill_value=1.e+20):
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

        # probably going to want to add to the history global attribute. From CF
        # conventions page: 
        # 
        # history: Provides an audit trail for modifications
        # to the original data. Well-behaved generic netCDF filters will
        # automatically append their name and the parameters with which they
        # were invoked to the global history attribute of an input netCDF file.
        # We recommend that each line begin by indicating the date and time of
        # day that the program was executed.

        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        history_entry = f"{current_time}: Saved dataset to {out_file}. Resampled to daily and cropped to aoi extent by temds.crujra.CRU_JRA_daily class, part of the Input_production project: https://github.com/uaf-arctic-eco-modeling/Input_production"
        if 'history' in self.dataset.attrs:
            self.dataset.attrs['history'] += "\n" + history_entry
        else:
            self.dataset.attrs['history'] = history_entry

        climate_enc = {
            '_FillValue':fill_value, 
            'missing_value':missing_value, 
            # 'zlib': True, 'complevel': 9 # USE COMPRESSION?
        }
        encoding = {var: climate_enc for var in self.vars}

        for axis in ['lat', 'lon', 'time']:
            encoding[axis] =  {
                '_FillValue':fill_value, 
                'missing_value':missing_value, 
                'dtype':'float'
            }
        
        
        self.dataset.to_netcdf(
            out_file, 
            encoding=encoding, 
            engine="netcdf4",
            unlimited_dims={'time':True}
        )
        

    def get_by_extent(self, minx, maxx, miny, maxy, resolution = None):
        """Returns xr.dataset for use in downscaling
        """
        return clip_xr_dataset(self.dataset,minx, maxx, miny, maxy, resolution )
