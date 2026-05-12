"""
Region
------

Objects for representing regions. The Region and SubregionGenerator classes
are designed as a replacement for earlier tile, and aoi related classes and
concepts.

TODO:
- implement apply_mask
- logger integration
- document import_datasource kwargs
- port other tile features over
- saving should fail by default if at any point a file exists including
        The region definition stuff?

"""
from pathlib import Path

import geopandas as gpd
import numpy as np
from osgeo import gdal
import pyproj
import xarray as xr
from joblib import Parallel, delayed
import shapely

# from ..gdal_tools import empty_dataset
from .. import corrections, downscalers

from ..logger import Logger
from ..datasources import dataset, timeseries
from .. import gdal_tools

from .mask import Mask
from .manifest import Manifest
from .tools import mask_boundary_compatibility_report, total_extent_as_geoseries
from temds.constants import TEMDS_DATASET_NAMES

class MaskBoundaryCompatibilityError(Exception):
    """Exception for region mask and  boundary incompatibility errors
    """
    pass

class Region(object):
    """
        This class represents a region to process data over. A Region has 
    a `boundary` (geopandas GeoSeries, or GeoDataFrame) and a `mask` (mask,Mask) 
    which define the spatial extent and properties of the region. A region also 
    has `data`, data is imported to the region to match the spatial properties 
    described by the `boundary` and the `mask`. RS_Logger style logging is 
    supported by this object. See `__init__` for documentation on how to set up 
    a Region object

        The only required item to create a Region is the boundary, but a mask 
    may also be provided. When a mask is not provided it is calculated from the 
    boundary, with all values set to 1, a resolution must be provided in this 
    case. When a boundary and a mask are provided they are evaluated based on 
    their CRS, transform and shape, and an Exception is raised if they are not.

    Attributes
    ----------
    boundary: geopandas.GeoDataFrame or geopandas.GeoSeries
        Single row GeoDataFrame, or GeoSeries used as region boundary. 
        defines crs of data
    mask: mask.Mask
        Mask object which defines resolution, transform of data
    logger: rs_logger.Logger
        Internal logging object
    """
    def __init__(
            self, boundary: gpd.GeoDataFrame | gpd.GeoSeries , 
            mask: Mask = None, logger: Logger =Logger(), **kwargs
        ): 
        """Create a region

        Parameters
        ----------
        boundary: geopandas.GeoDataFrame or geopandas.GeoSeries
            Single row GeoDataFrame, or GeoSeries used as region boundary. 
        mask: mask.Mask, Optional
            Mask object which defines resolution, transform of data.
            Will be created from boundary in not provided. When not 
            provided 'resolution` key word argument must be provided.
            Created mask will assume uniform pixel size, and north
            up format for raster
        logger: rs_logger.Logger
        kwargs:
            'resolution': number
                Resolution in boundary.CRS units
        
        Raises
        ------
        MaskBoundaryCompatibilityError
            Will be raised if the CRS, transform or shapes, of the 
            boundary or mask are incompatible
        """
        try:
            self.boundary = boundary.reset_index()
        except: # index is already reset
            self.boundary = boundary
        try:
            del(self.boundary['level_0']) # if this is there we don't want it
        except KeyError:
            pass
        if mask:
            self.mask = mask
        else:
            resolution = kwargs['resolution']
            self.mask = Mask.from_extent(boundary, resolution) 

        self.data = {} 
        self.logger = logger
        self.name = kwargs['name'] if 'name' in kwargs else "Unnamed"

        if not('bypass_checks' in kwargs and kwargs['bypass_checks'] == True):
            self.check_mask_compatibility(self.mask)


    def __repr__(self):
        """String Representation"""
        data = ', '.join(self.data.keys())
        msg = f'Region: {self.name} (CRS: {self.crs.name}, Bounds: {self.boundary.total_bounds}, Resolution: {self.resolution}) with data for: {data}'
        return msg

    def get_extent(self, crs=None, align_to=None):

        boundary = self.boundary
        if crs:
            boundary = boundary.to_crs(crs)

        return total_extent_as_geoseries(boundary, align_to).total_bounds


    def check_mask_compatibility(self, mask):
        """Checks that a mask is compatible with `boundary`
        Parameters
        ----------
        mask: mask.Mask
            Mask object

        Raises
        ------
        MaskBoundaryCompatibilityError
            Will be raised if the CRS, transform or shapes, of the 
            boundary or mask are incompatible
        """
        report = mask_boundary_compatibility_report(mask, self.boundary)
        if not report[0]:
            raise MaskBoundaryCompatibilityError(
                '`mask` CRS and `boundary` crs do not match'
            )
        if not report[1]:
            raise MaskBoundaryCompatibilityError(
                '`mask` shape, and calculated `boundary` shape do not match'
            )
        if not report[2]:
            raise MaskBoundaryCompatibilityError(
                '`mask` transform , and calculated `boundary` transform do not match'
            )

    @property
    def resolution(self) -> tuple:
        """Resolution is defined by the mask dataset"""
        return self.mask.resolution
    
    @property
    def crs(self) -> pyproj.CRS:
        """CRS of region"""
        return self.boundary.crs
    
    @property
    def transform(self) -> tuple:
        """Gdal formatted crs"""
        return self.mask.transform
    
    @property
    def shape(self) -> tuple:
        """2d shape of region as x,y """
        return self.mask.shape

    def apply_mask(self, keys: list = None, no_data_val: int| float = None, mask: Mask=None):
        """set values to no data where mask (internal, or provided) is == 0

        Parameters
        ----------
        keys: list, optional
            Optional list of items in `data` to apply mask to. When not 
        provided all items will have mask applied.
        no_data_val: number, optional
            No data val to use, When not provided will pull no data from
            each dataset
        mask: Mask, Optional
            A mask to apply, when not provided will use internal `mask` attr.
            Must be compatible with Boundary
        
        Raises
        ------
        MaskBoundaryCompatibilityError
            Will be raised if the CRS, transform or shapes, of the 
            boundary or mask are incompatible

        """
        # if keys is None:
        #     keys = self.data.keys()
        # if mask is None:
        #     mask = self.mask
        # self.check_mask_compatibility(mask)
        pass

    @classmethod
    def from_mask(cls, mask:Mask,logger: Logger = Logger(), **kwargs):
        return cls(mask.export_gpd_extent(), mask, logger, **kwargs)
    
    @classmethod
    def from_TEMDataset(cls, temds, logger: Logger = Logger(), **kwargs):
        """
        """
        minx, miny, maxx, maxy = temds.extent
        extent = gpd.GeoSeries(shapely.box(minx, miny, maxx, maxy ), [0], temds.crs)
        mask = Mask.from_extent(extent, abs(temds.resolution[0]), False, True)
        return cls.from_mask(mask, logger, **kwargs)

    @classmethod
    def from_directory(cls, directory: Path, import_data: list = None, logger: Logger = Logger()):
        """Create a Region from a directory containing a manifest file

        TODO: Parallel option here?

        Parameters
        ----------
        directory: Path
            a directory containing a manifest file, and data which the manifest
            describes
        logger: rs_logger.Logger

        Returns
        -------
        Region
        """
        manifest = Manifest.from_file( directory/ 'manifest.yml' )
        boundary = gpd.read_file(directory / manifest['boundary'] )
        mask = Mask.from_file(directory / manifest['mask'])
        new = cls(boundary, mask, logger, name=directory.stem)

        if import_data is None:
            import_data = manifest['data'].keys()
            

        # if import_data:
        if import_data != []:
            logger.info('Region.from_directory: Importing data')
            for item in import_data:
                _file = manifest['data'][item]
                in_path = Path(directory).joinpath(_file)
                logger.info(f'... {item} from {in_path}')
                logger.suspend()
                if in_path.is_dir():
                    temp = timeseries.YearlyTimeSeries(
                        in_path, 
                        logger = new.logger
                    )
                else:
                    temp = dataset.TEMDataset(
                        in_path, logger = new.logger
                    )
                new.import_datasource(item, temp)
                logger.resume()
        else:
            logger.info('Region.from_directory: Skipping data import')

        return new
    
    def check_datasource(self, datasource):
        """checks if a datasource already matches the region"""
        gt_check = self.transform == datasource.transform.to_gdal()
        # print('region-check', self.transform, datasource.transform.to_gdal())
        crs_check = self.crs == datasource.crs
        shape_check = self.shape == datasource.shape
        # print( gt_check, crs_check, shape_check)
        return gt_check and crs_check and shape_check

    def lazy_import(self, where, ds_name_key):
        """
        Tries to look in `where` for a manifest file. Then looks in manifest for
        an entry corresponding to `ds_name_key`. If it finds one it imports that
        dataset and adds it to the region data with the key `ds_name_key`. If it
        does not find one it raises an error. This is designed to be used when a
        dataset is required for a region but is not currently loaded in the
        region data. This allows the region to import only the data it needs for
        export without having to load everything at the start.
        """
        self.logger.info(f"{ds_name_key} data not found in region data. Attempting to read manifest and import {ds_name_key} data...")

        manifest = Manifest.from_file( Path(where) / 'manifest.yml' )
        if ds_name_key not in manifest['data'].keys():
            raise KeyError(f"{ds_name_key} not found in manifest data. Cannot lazy import {ds_name_key}. Please ensure the manifest file in {where} has an entry for {ds_name_key} in the data section.")
        _file = manifest['data'][ds_name_key]
        in_path = Path(where).joinpath(_file)
        self.logger.info(f'... {ds_name_key} from {in_path}')
        self.logger.suspend()
        if in_path.is_dir():
            _ds = timeseries.YearlyTimeSeries(
                in_path, 
                logger = self.logger
            )
        else:
            _ds = dataset.TEMDataset(
                in_path, logger = self.logger
            )
        self.import_datasource(ds_name_key, _ds)
        self.logger.resume()

    
    def import_datasource(self, name, datasource, callback = None, **kwargs):
        """Loads an item to `data` as name from a datasource. Each datasource 
        may be a ...

        Parameters
        ----------
        name: str
            used as key for datasource in `data`
        datasource: Object
            Object must implement `get_by_extent` with 6 arguments
            (minx: float, maxx: float, miny: float, maxy: float, 
            extent_crs: pyproj.crs.crs.CRS, resolution: float)
        callback: function, Optional
            Call back to apply to data after loading is performed
        **kwargs:
            
        """
        minx, miny, maxx, maxy = self.boundary.bounds[
            ['minx', 'miny', 'maxx', 'maxy']
        ].iloc[0]
        

        kwargs['resolution'] = self.resolution


        self.logger.info(
            f'importing {name} from {datasource} for the extent: {minx}, {miny}, {maxx}, {maxy}.'
        )
        if self.check_datasource(datasource): # the datasource is region ready
            # print('region Ready')
            self.data[name] = datasource
        else:
            kwargs['dest_gt'] = self.mask.raster.GetGeoTransform()
            self.data[name] = datasource.get_by_extent(
                minx, miny, maxx, maxy, self.crs, **kwargs
            )
        if callback is not None:
            if isinstance( self.data[name], dataset.TEMDataset ):
                self.data[name].dataset = callback(self.data[name].dataset, self.logger, **kwargs)
            else:
                self.data[name].apply_callback(callback, **kwargs)
                # for year in self.data[name].range():
                #     self.data[name][year].dataset = callback(self.data[name][year].dataset, self.logger, **kwargs)

    def export_dataset(self, where, name, **kwargs):
        """Exports a item in `data` to a file (TEMDataset) or files (Timeseries)
        """
        where = Path(where)

        self.data[name].save(where, **kwargs)

    def export_timeseries(self, where, name, **kwargs):
        """Exports a item in `data` to a file (TEMDataset) or files (Timeseries)
        """
        where = Path(where) / name
        self.data[name].save(where, name+'-{year}.nc' , **kwargs)
       
    def export_boundary(self, where):
        self.boundary.to_file( where )

    def export_mask(self, where):
        self.mask.to_file( where )

    def export_to_directory(self, where: Path, format: str = 'TEMDS', **kwargs
            # boundary_filename = 'boundary.geojson',
            # mask_filename = 'mask.tif',
            # manifest_filename = 'manifest.yml',
            # update_manifest = 
            
        ):
        # TODO: Should this actually be the wrapper for exporting to a specific
        # format???
        """

        """

        lookup = lambda kw, ke, de: kw[ke] if ke in kw else de

        to_save = lookup(kwargs, 'items', 'all')
        boundary_filename = lookup(kwargs, 'boundary_filename', 'boundary.geojson')
        mask_filename = lookup(kwargs, 'mask_filename', 'mask.tif')
        manifest_filename = lookup(kwargs, 'manifest_filename', 'manifest.yml')
        update_manifest = lookup(kwargs, 'update_manifest', False)

        manifest = Manifest()

        if to_save == 'all':
            to_save = list(self.data.keys())

        where.mkdir(exist_ok=True, parents=True)

        self.export_boundary(where / boundary_filename)
        manifest['boundary'] = boundary_filename
        self.export_mask( where/ mask_filename )  
        manifest['mask'] = mask_filename

        for name in to_save:
            print(name)
            try:
                ds_where = where / f'{name}.nc' 
                self.export_dataset(ds_where, name, **kwargs)
                manifest['data'][name] = f'{name}.nc' 
            except TypeError:
                ds_where = where 
                self.export_timeseries(ds_where, name, **kwargs)
                manifest['data'][name] = f'{name}'
           

        manifest_file = where / manifest_filename
        if manifest_file.exists() and update_manifest:
            old = Manifest.from_file(manifest_file)
            man_data = old['data']
            man_data.update(manifest['data'])
            manifest['data'] = man_data

        manifest.to_file(manifest_file)
        return manifest


    def export_TEM(self, dataset_name, where, **kwargs):
        """Exports a item in `data` to a TEM ready format.
        dataset_name: str 
            should be a key in self.data which corresponds to a dataset which
            can be exported to TEM format.
        where: Path
            directory to save exported data to. Will be created if it does not
            exist. Data will be saved to this directory with the name
            {dataset_name}.nc, where dataset_name is the value of the
            dataset_name parameter.

        Questions:
         - should this export all data in a region object? Not all possible keys
           have a tem analog
         - should there be something that lets user specifiy which things to
           export?
         - should there be any validation? validation that the TEM dataset is
           complete?
         - should there be a return type? like an xarray dataset? Or should this
           function actually write the files?
         -

        """
        function_name = 'Region.export_TEM'

        if dataset_name not in TEMDS_DATASET_NAMES:
            raise NotImplementedError(f"Invalid dataset name for TEM export: {dataset_name}. Must be one of {TEMDS_DATASET_NAMES}.")

        # Not really sure about this.....
        assert self.name == where.stem, f"Region name {self.name} does not match destination directory name {where.stem}. Please ensure the destination directory is named the same as the region you want to export."  


        destination = where / "tem_export"
        destination.mkdir(exist_ok=True, parents=True)

        if dataset_name == 'co2':
            self.logger.info("Exporting CO2 data to TEM format...")

            # TODO: Refactor this to get data from the web or at least a
            # file instead of hard coding here...

            # Manually spliced data from NOAA ESRL Global Monitoring Division
            # with the data from the demo file. (just added yrs 2016+)
            # https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_annmean_mlo.txt
            co2 = [296.311, 296.661, 297.04, 297.441, 297.86, 298.29, 298.726, 299.163, 
                299.595, 300.016, 300.421, 300.804, 301.162, 301.501, 301.829, 302.154, 
                302.48, 302.808, 303.142, 303.482, 303.833, 304.195, 304.573, 304.966, 
                305.378, 305.806, 306.247, 306.698, 307.154, 307.614, 308.074, 308.531, 
                308.979, 309.401, 309.781, 310.107, 310.369, 310.559, 310.667, 310.697, 
                310.664, 310.594, 310.51, 310.438, 310.401, 310.41, 310.475, 310.605, 
                310.807, 311.077, 311.41, 311.802, 312.245, 312.736, 313.27, 313.842, 
                314.448, 315.084, 315.665, 316.535, 317.195, 317.885, 318.495, 318.935, 
                319.58, 320.895, 321.56, 322.34, 323.7, 324.835, 325.555, 326.55, 
                328.455, 329.215, 330.165, 331.215, 332.79, 334.44, 335.78, 337.655, 
                338.925, 340.065, 341.79, 343.33, 344.67, 346.075, 347.845, 350.055, 
                351.52, 352.785, 354.21, 355.225, 356.055, 357.55, 359.62, 361.69, 
                363.76, 365.83, 367.9, 368, 370.1, 372.2, 373.6943, 375.3507, 377.0071, 
                378.6636, 380.5236, 382.3536, 384.1336, 389.9, 391.65, 393.85, 396.52, 
                398.65, 400.83,
                404.41, 406.76, 408.72, 411.65, 414.21, 416.41, 418.53, 421.08, 424.61 ]
            year = [1901, 1902, 1903, 1904, 1905, 1906, 1907, 1908, 1909, 1910, 1911, 
                1912, 1913, 1914, 1915, 1916, 1917, 1918, 1919, 1920, 1921, 1922, 1923, 
                1924, 1925, 1926, 1927, 1928, 1929, 1930, 1931, 1932, 1933, 1934, 1935, 
                1936, 1937, 1938, 1939, 1940, 1941, 1942, 1943, 1944, 1945, 1946, 1947, 
                1948, 1949, 1950, 1951, 1952, 1953, 1954, 1955, 1956, 1957, 1958, 1959, 
                1960, 1961, 1962, 1963, 1964, 1965, 1966, 1967, 1968, 1969, 1970, 1971, 
                1972, 1973, 1974, 1975, 1976, 1977, 1978, 1979, 1980, 1981, 1982, 1983, 
                1984, 1985, 1986, 1987, 1988, 1989, 1990, 1991, 1992, 1993, 1994, 1995, 
                1996, 1997, 1998, 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 
                2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 
                2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]

            self.logger.info(f"Saving file to {destination / 'co2.nc'}...")
            xr.Dataset(data_vars={'co2':('year',co2)}, coords={'year':year}).to_netcdf(destination / 'co2.nc')
            return 0

        if dataset_name == 'topo':
            self.logger.info("Exporting topo data to TEM format...")
            if dataset_name not in self.data.keys():
                self.lazy_import(where, 'topo')

            self.logger.info("Converting topo data to TEM format...")
            T = self.data['topo'].dataset.drop(['TPI', 'drainage_class'])

            T['Y'] = np.arange(T.sizes['y'])
            T['X'] = np.arange(T.sizes['x'])

            self.logger.info(f"Saving file to {destination / 'topo.nc'}...")
            T.to_netcdf(destination / 'topo.nc')
            return 0

        if dataset_name == 'drainage':
            self.logger.info("Exporting drainage data to TEM format...")
            if 'topo' not in self.data.keys():
                self.lazy_import(where, 'topo')

            self.logger.info("Converting drainage data to TEM format...")
            D = self.data['topo'].dataset.drop(['elevation', 'TPI', 'slope', 'aspect'])
            D['Y'] = np.arange(D.sizes['y'])
            D['X'] = np.arange(D.sizes['x'])
            self.logger.info(f"Saving file to {destination / 'drainage.nc'}...")
            D.to_netcdf(destination / 'drainage.nc')
            return 0

        if dataset_name == 'runmask':
            self.logger.info("Exporting runmask data to TEM format...")
            self.logger.info("...using vegetation data to create runmask...")
            if 'vegetation' not in self.data.keys():
                self.lazy_import(where, 'vegetation')
            veg_ds = self.data['vegetation'].dataset
            mask = veg_ds.copy()
            mask = mask.rename({'veg_class':'run'})

            self.logger.info("turn on mask for all valid veg class px...")
            mask['run'] = (('y','x'), np.where(veg_ds['veg_class'] > 0, 1, 0))
            mask['Y'] = np.arange(mask.sizes['y'])
            mask['X'] = np.arange(mask.sizes['x'])
            self.logger.info(f"Saving file to {destination / 'run-mask.nc'}...")
            mask.to_netcdf(destination / 'run-mask.nc')

            return 0

        if dataset_name == 'vegetation':

            self.logger.info("Exporting vegetation data to TEM format...")
            if dataset_name not in self.data.keys():
                self.lazy_import(where, 'vegetation')

            self.logger.info("Converting vegetation data to TEM format...")
            V = self.data[dataset_name].dataset
            V['Y'] = np.arange(V.sizes['y'])
            V['X'] = np.arange(V.sizes['x'])
            self.logger.info(f"Saving file to {destination / 'veg.nc'}...")
            V.to_netcdf(destination / 'veg.nc')
            return 0

        if dataset_name == 'soiltex':
            self.logger.info("Exporting soil texture data to TEM format...")
            if dataset_name not in self.data.keys():
                self.lazy_import(where, 'soiltex')

            self.logger.info("Converting soil texture data to TEM format...")
            ST = self.data[dataset_name].dataset
            ST['Y'] = np.arange(ST.sizes['y'])
            ST['X'] = np.arange(ST.sizes['x'])
            self.logger.info(f"Saving file to {destination / 'soiltex.nc'}...")
            ST.to_netcdf(destination / 'soiltex.nc')
            return 0

        if dataset_name == 'cru_climate' or dataset_name == 'cmip_climate':

            if dataset_name == 'cru_climate':
                ds_key_name = 'crujra-downscaled'
                if 'crujra-downscaled' not in self.data.keys():
                    self.lazy_import(where, 'crujra-downscaled')
            if dataset_name == 'cmip_climate':
                ds_key_name = 'cmip6-ssp245-downscaled'
                if 'cmip6-ssp245-downscaled' not in self.data.keys():
                    self.lazy_import(where, 'cmip6-ssp245-downscaled')

            target_vars = {
                'tair_avg': 'mean', 
                'vapo': 'mean', 
                'nirr': 'mean',
                'prec': 'sum'
            }

            new_names = {
                'tair_avg':'tair', 
                'vapo':'vapor_press', 
                'nirr':'nirr', 
                'prec':'precip'
            }

            ds_monthly = self.data[ds_key_name].synthesize_to_monthly(target_vars, new_names)

            transformer = pyproj.Transformer.from_crs(self.data[ds_key_name].data[0].dataset.rio.crs.to_epsg(), 4326)

            X, Y = np.meshgrid(self.data[ds_key_name].data[0].dataset['x'].values, self.data[ds_key_name].data[0].dataset['y'].values)

            LATS, LONS = transformer.transform(X, Y)

            self.logger.info("Adding latitude and longitude coordinates to dataset...")
            ds_monthly['lat'] = (('y','x'), LATS)
            ds_monthly['lat'].attrs['long_name'] = 'latitude'
            ds_monthly['lat'].attrs['units'] = 'degrees_north'
            ds_monthly['lat'].attrs['standard_name'] = 'latitude'

            ds_monthly['lon'] = (('y','x'), LONS)
            ds_monthly['lon'].attrs['long_name'] = 'longitude'
            ds_monthly['lon'].attrs['units'] = 'degrees_east'
            ds_monthly['lon'].attrs['standard_name'] = 'longitude'

            ds_monthly['X'] = np.arange(ds_monthly.sizes['x'])
            ds_monthly['Y'] = np.arange(ds_monthly.sizes['y'])

            self.logger.warn("Replacing any NaN or inf values in nirr with 0...")
            np.nan_to_num(ds_monthly['nirr'], copy=False, nan=0.0, posinf=0.0, neginf=0.0)

            if dataset_name == 'cru_climate':
                outname = 'crujra-downscaled-historic-climate.nc'
            elif dataset_name == 'cmip_climate':
                outname = 'cmip6-ssp245-downscaled-projected-climate.nc'
            else:
                assert False, "This should never happen"
            self.logger.info(f"Saving file to {destination / outname}...")
            ds_monthly.to_netcdf(destination / outname) 

            return 0

        if dataset_name == 'fri_fire':
            self.logger.info("Exporting FRI fire data to TEM format...")
            if 'fri-fire' not in self.data.keys():
                self.lazy_import(where, 'fri-fire')
            self.logger.info("Converting FRI fire data to TEM format...")
            F = self.data['fri-fire'].dataset
            F['Y'] = np.arange(F.sizes['y'])
            F['X'] = np.arange(F.sizes['x'])
            self.logger.info(f"Saving file to {destination / 'fri-fire.nc'}...")
            F.to_netcdf(destination / 'fri-fire.nc')
            return 0

        if dataset_name == 'historic_explicit_fire' or dataset_name == 'projected_explicit_fire':
            self.logger.info("Exporting explicit fire data to TEM format...")
            self.logger.warn("SYNTHETIC DATA ONLY AT THIS TIME.")

            # The process for creating "real" explicit fire data has not been
            # developed yet, so for now we just make some synthetic data so that
            # TEM will run without complaint. The fire module is effectively off
            # because we set the burn mask to all zero. The data must match the
            # shape of the climate files so we simply copy those and rename the
            # variables. This avoids the need to create the synthetic data at
            # daily resolution and then resample to monthly, which would be
            # necessary if we try to make the synthetic data from scratch.

            target_vars = {
                'tair_avg': 'mean', 
                'vapo': 'mean', 
                'nirr': 'mean',
                'prec': 'sum'
            }

            new_names = {
                'tair_avg':'exp_burn_mask', 
                'vapo':'exp_area_of_burn', 
                'nirr':'exp_jday_of_burn', 
                'prec':'exp_fire_severity'
            }

            if 'historic' in dataset_name:
                self.logger.info("Pulling time axis from cru...")
                ds_key = 'crujra-downscaled'
                out_name = 'historic-explicit-fire.nc'
            elif 'projected' in dataset_name:
                self.logger.info("Pulling time axis from cmip...")
                ds_key = 'cmip6-ssp245-downscaled'
                out_name = 'projected-explicit-fire.nc'
            else:
                assert False, f"{function_name}: the dataset_name must contain either 'historic' or 'projected'"

            ds_monthly = self.data[ds_key].synthesize_to_monthly(target_vars, new_names)

            for v in new_names.values():
                ds_monthly[v].values = np.ones(ds_monthly[v].shape)    

            self.logger.info('Setting attributes for data variables')
            ds_monthly['exp_burn_mask'].attrs.update(units='', name='Fire Occurrence')
            ds_monthly['exp_fire_severity'].attrs.update(units='', name='Fire Severity')
            ds_monthly['exp_jday_of_burn'].attrs.update(units='', name='Julian Day of Burn')
            ds_monthly['exp_area_of_burn'].attrs.update(units='km-2', name='Area of Burn (km-2)')

            # Turning explicit fire OFF for all grid cells and time steps.
            ds_monthly['exp_burn_mask'].values = np.zeros(ds_monthly['exp_area_of_burn'].shape)

            ds_monthly['exp_burn_mask'] = ds_monthly['exp_burn_mask'].astype(np.int32)
            ds_monthly['exp_jday_of_burn'] = ds_monthly['exp_jday_of_burn'].astype(np.int32)
            ds_monthly['exp_fire_severity'] = ds_monthly['exp_fire_severity'].astype(np.int32)
            ds_monthly['exp_area_of_burn'] = ds_monthly['exp_area_of_burn'].astype(np.int64)

            ds_monthly['X'] = np.arange(ds_monthly.sizes['x'])
            ds_monthly['Y'] = np.arange(ds_monthly.sizes['y'])

            ds_monthly['exp_burn_mask'] = ds_monthly['exp_burn_mask'].rename({'y': 'Y', 'x': 'X'})
            ds_monthly['exp_jday_of_burn'] = ds_monthly['exp_jday_of_burn'].rename({'y': 'Y', 'x': 'X'})
            ds_monthly['exp_fire_severity'] = ds_monthly['exp_fire_severity'].rename({'y': 'Y', 'x': 'X'})
            ds_monthly['exp_area_of_burn'] = ds_monthly['exp_area_of_burn'].rename({'y': 'Y', 'x': 'X'})

            self.logger.info(f"Saving file to {destination / out_name}...")
            ds_monthly.to_netcdf(destination / out_name)

            return 0


    def empty_gdal_dataset(self, n_layers=1, dtype = gdal.GDT_Float32):
        """Create an empty gdal raster based on regions extent/crs/transform
        """
        _x, _y = self.shape
        
        new = gdal_tools.empty_dataset(
            _x, _y, self.crs.to_wkt(), self.transform, n_layers, dtype
        )
        return new

    ## much of he tile stuff should move here

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
        self.data[target] = dataset.TEMDataset(
                self.data[source].create_climate_baseline(
                start_year, end_year, **kwargs
            )
        )

    def calculate_correction_factors(
            self, baseline_id, reference_id, variables, 
            factor_id='correction-factors'
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
        reference = self.data[reference_id].dataset
        baseline = self.data[baseline_id].dataset
        temp = []


        # for var, info in variables.items():
        for var in variables:
            func = corrections.LOOKUP[var]
            self.logger.info(f'.. Calculating correction factor for {var} with {func}')

            current = func(baseline[var], reference[var])
            current.name = var
            temp.append(current)
           

        correction_factors = xr.merge(temp)
        self.data[factor_id] = dataset.TEMDataset(correction_factors)

    def delta_downscale_year(self, year, source_id, correction_id, variables):
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
        correction = self.data[correction_id].dataset
        source = self.data[source_id][year].dataset
        temp = []
        
        self.logger.info(f'.. Downscaling {year}')
        for var in variables:
            func = downscalers.LOOKUP[var]
            self.logger.debug(f'.. Downscaling {var} with {func}')
            src = source[var]
            try:
                cf = correction[var]
            except KeyError:
                cf = 0 # not used
            current = func(src, cf)
            
            
            current.name = var
            temp.append(current)
        
        downscaled = xr.merge(temp)
        downscaled.attrs['data_year'] = year

        
        downscaled.rio.set_spatial_dims(x_dim="x", y_dim="y", inplace=True)
        downscaled.rio.write_crs(source.rio.crs, inplace=True)
        downscaled.rio.write_coordinate_system(inplace=True) 
        downscaled.rio.write_transform(source.rio.transform(), inplace=True)

        return dataset.YearlyDataset(year, downscaled)

    def delta_downscale_timeseries(self, downscaled_id, source_id, correction_id, variables, parallel=False, years=None):
        """
        Add downscaled to self.data dict as xarray dataset. 
        """
        print(source_id, correction_id, variables)
        if not years:
            years = self.data[source_id].range()
        else:
            years = range(years[0], years[1]+1)
        
        if parallel:
            ## The open raster in mask breaks parallelization, so remove it 
            ## for now, and add it back at the end
            mask_backup = self.mask
            self.mask=""
            results = Parallel()(
                delayed(self.delta_downscale_year)(
                    int(year), 
                    source_id, 
                    correction_id, 
                    variables
                    ) for year in self.data[source_id].range()
            )
            self.mask = mask_backup
        else:
            results = []
            for year in years:
                # print(year, type(year))
                # self.logger.info(f'Downscaling {year}')
                data = self.delta_downscale_year(year, source_id, correction_id, variables)
                results.append(data)
        
        self.data[downscaled_id] = timeseries.YearlyTimeSeries(results)

