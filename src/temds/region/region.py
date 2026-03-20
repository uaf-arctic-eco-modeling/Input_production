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

"""
from pathlib import Path

import shapely
import geopandas as gpd
from osgeo import gdal
import pyproj
import yaml



from ..gdal_tools import empty_dataset

from ..logger import Logger
from ..datasources import dataset, timeseries

from .mask import Mask
from .manifest import Manifest
from .tools import mask_boundary_compatibility_report

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
        self.boundary = boundary.reset_index()
        if mask:
            self.mask = mask
        else:
            resolution = kwargs['resolution']
            self.mask = Mask.from_extent(boundary, resolution) 

        self.data = {} 
        self.logger = logger
        self.check_mask_compatibility(self.mask)


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
    def from_directory(cls, directory: Path, logger: Logger = Logger()):
        """Create a Region from a directory containing a manifest file

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

        for item, _file in manifest['data'].items():
            in_path = Path(directory).joinpath(_file)
            if in_path.is_dir():
                new.data[item] = timeseries.YearlyTimeSeries(
                    in_path, 
                    logger = new.logger
                )
            else:
                new.data[item] = dataset.TEMDataset(
                    in_path, logger = new.logger
                )
        return new

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
        kwargs['dest_gt'] = self.mask.raster.GetGeoTransform()
        self.data[name] = datasource.get_by_extent(
            minx, miny, maxx, maxy, self.crs, **kwargs
        )
        if callback is not None:
            if isinstance(self.data[name], dataset.TEMDataset ):
                self.data[name].dataset = callback(self.data[name].dataset, self.logger, **kwargs)
            else:
                for year in self.data[name].range():
                    self.data[name][year].dataset = callback(self.data[name][year].dataset, self.logger, **kwargs)

    def export_dataset(self, where, name, **kwargs):
        """Exports a item in `data` to a file (TEMDataset) or files (Timeseries)
        """
        self.data[name].save(where, **kwargs)
       
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

        to_save = lookup(kwargs, 'items', self.data.keys())
        boundary_filename = lookup(kwargs, 'boundary_filename', 'boundary.geojson')
        mask_filename = lookup(kwargs, 'mask_filename', 'mask.tif')
        manifest_filename = lookup(kwargs, 'manifest_filename', 'manifest.yml')
        update_manifest = lookup(kwargs, 'update_manifest', False)

        manifest = Manifest()

        where.mkdir(exist_ok=True, parents=True)

        self.export_boundary(where / boundary_filename)
        manifest['boundary'] = boundary_filename
        self.export_mask( where/ mask_filename )  
        manifest['mask'] = mask_filename

        for name in to_save:
            ds_where = where / f'{name}.nc' 
            self.export_dataset(ds_where, name, **kwargs)
            manifest['data'][name] = f'{name}.nc' 

        manifest_file = where / manifest_filename
        if manifest_file.exists() and update_manifest:
            old = Manifest.from_file(manifest_file)
            man_data = old['data']
            man_data.update(manifest['data'])
            manifest['data'] = man_data

        manifest.to_file(manifest_file)
        return manifest

    ## much of he tile stuff should move here


class SubregionGenerator(object):
    def __init__(self, full_region, tile_size_x=100, tile_size_y=100):
        self.full_region = full_region
        self.tile_size_x = tile_size_x
        self.tile_size_y = tile_size_y
        self.tile_index = self._create_tile_index()
        
    def get_tile_gridsize(self):
    
        maskX = self.full_region.mask.raster.RasterXSize
        maskY = self.full_region.mask.raster.RasterYSize
        
        N_TILES_X = int(maskX / self.tile_size_x)
        N_TILES_Y = int(maskY / self.tile_size_y)
        
        if maskX % self.tile_size_x > 0:
            N_TILES_X += 1
        
        if maskX % self.tile_size_y > 0:
            N_TILES_Y += 1
        
        return N_TILES_X, N_TILES_Y

    def _create_tile_index(self):
        '''
        Chop a raster up into tiles.
        Returns list of tile extent dictionaries. Each dict will have x, y, minx
        and max (projection coords) and H and V indices in the tileset. And the
        resolution.
        '''
        maskX = self.full_region.mask.raster.RasterXSize
        maskY = self.full_region.mask.raster.RasterYSize
    
        aoiGT = self.full_region.mask.raster.GetGeoTransform()
        geotransform = aoiGT
        
        minx = geotransform[0]
        miny = geotransform[3]
        maxx = minx + geotransform[1] * maskX
        maxy = miny + geotransform[5] * maskY
        aoi_extents = dict(minx=minx, miny=miny, maxx=maxx, maxy=maxy)
    
        
    
        N_tiles_X, N_tiles_Y = self.get_tile_gridsize()
    
        tile_extents = []
    
        for h in range(N_tiles_X):
          for v in range(N_tiles_Y):
    
            tile_xmin = aoi_extents['minx'] + self.tile_size_x * h * aoiGT[1]
            if (h+1) == len(range(N_tiles_X)):
              tile_xmax = tile_xmin + (maskX % self.tile_size_x) * aoiGT[1]
            else:
              tile_xmax = tile_xmin + self.tile_size_x * aoiGT[1]
    
            tile_pixelXsize = aoiGT[1]
            tile_pixelYsize = aoiGT[5]
    
            # Origin LOWER LEFT
            tile_ymin = aoi_extents['miny'] + tile_pixelYsize * maskY \
                        + self.tile_size_y * v * tile_pixelYsize * -1
            if (v+1) == len(range(N_tiles_Y)):
              tile_ymax = tile_ymin + (maskY % self.tile_size_y) * tile_pixelYsize * -1
            else:
              tile_ymax = tile_ymin + self.tile_size_y * tile_pixelYsize * -1 
    
            # # Origin UPPER LEFT 
            # tile_ymin = aoi_extents['miny'] + TILE_SIZE_Y * v * aoiGT[5]
            # if (v+1) == len(range(N_tiles_Y)):
            #   tile_ymax = tile_ymin + (maskY % TILE_SIZE_Y) * aoiGT[5]
            # else:
            #   tile_ymax = tile_ymin + TILE_SIZE_Y * aoiGT[5]
    
            tile_extents.append(dict(
                H=h, V=v, 
                geometry = shapely.box(tile_xmin, tile_ymin, tile_xmax, tile_ymax),
                )
            )

        tile_index = gpd.GeoDataFrame(tile_extents, crs = self.full_region.boundary.crs)
        return tile_index

    def generate_tile(self, index):

        tile_info = self.tile_index.loc[index]

        minx, miny, maxx, maxy = self.tile_index.loc[0].geometry.bounds
        
        _, resx, _, _, _, resy =  self.full_region.mask.raster.GetGeoTransform()
        
        nx, ny = abs((maxx-minx)/resx), abs((maxy-miny)/resy)

        proj = self.full_region.boundary.crs.to_wkt()
        gt = minx, resx, 0, maxy, 0, resy
        
        new_mask = empty_dataset(
            int(nx), int(ny), proj, gt, 
            bands=1, gdal_type=gdal.GDT_Int16
        )
        
        
        gdal.Warp(new_mask, self.full_region.mask.raster)

        subregion = Region(self.tile_index.loc[[index]], new_mask)

        for name, ds in self.full_region.data.items():
            subregion.import_from_datasource(name, ds)

        return subregion
