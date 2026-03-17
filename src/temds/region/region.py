"""

"""
# https://gcmeval.met.no/
from pathlib import Path

import shapely
import geopandas as gpd
from osgeo import gdal
import yaml
from collections import UserDict


from ..gdal_tools import empty_dataset

from .logger import Logger
from .datasources import dataset, timeseries


class Manifest(UserDict):
    def __init__(self):
        self.data = {
            'data': {}
        }

    @classmethod
    def from_file(cls, where):
        new = cls()
        with Path(where).open('r') as fd:
            new.data = yaml.load(fd, yaml.Loader)
        return new
        

    def to_file(self, where):
        with where.open('w') as fd:
            yaml.safe_dump(self.items, fd, sort_keys=False)

    # def update(self, new):
      

class RegionOfInterest(object):
    def __init__(self, vector, mask, logger=Logger()):
        self.boundary = vector #GeoDataFrame or GeoSeries with single row limit to single polygon?
        self.data = {}
        self.mask = mask

    @property
    def resolution(self):
        """Resolution is defined by the mask dataset
        """
        return self.mask.resolution

    def import_from_directory(self, directory: Path):
        pass

    ## rename this
    def import_from_datasource(self, name, datasource, buffered=True, callback = None, **kwargs):
        pass
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


        self.logger.info(
            f'importing {name} from {datasource} for the extent: {extent}'
        )
        self.data[name] = datasource.get_by_extent(
            minx, miny, maxx, maxy, self.crs, **kwargs
        )
        if callback is not None:
            if isinstance(self.data[name], dataset.TEMDataset ):
                self.data[name].dataset = callback(self.data[name].dataset, self.logger, **kwargs)
            else:
                for year in self.data[name].range():
                    self.data[name][year].dataset = callback(self.data[name][year].dataset, self.logger, **kwargs)



    def export_dataset(self, where, name):
        self.data[name].save(where)
       
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

        self.export_boundary(where / boundary_filename)
        manifest['boundary'] = boundary_filename
        self.export_mask( where/ mask_filename )  
        manifest['mask'] = mask_filename

        for name in self.data:
            ds_where = where / f'{name}.nc' 
            self.export_dataset(ds_where, name)
            manifest['data'][name] = f'{name}.nc' 

        manifest_file = where / manifest_filename
        if manifest_file.exists() and update_manifest:
            old = Manifest.from_file(manifest_file)
            man_data = old['data']
            man_data.update(manifest['data'])
            manifest['data'] = man_data

        manifest.to_file(manifest_file)





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

        subregion = RegionOfInterest(self.tile_index.loc[[index]], new_mask)

        # for name, ds in self.full_region.data.items():
            # subregion.import_and_normalize(...)

        return subregion
