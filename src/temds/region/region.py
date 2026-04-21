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
        new = cls(boundary, mask, logger)

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

    def export_to_directory(self, where: Path, **kwargs
            # boundary_filename = 'boundary.geojson',
            # mask_filename = 'mask.tif',
            # manifest_filename = 'manifest.yml',
            # update_manifest = 
            
        ):
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

