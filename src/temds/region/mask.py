"""
"""
from pathlib import Path
from copy import deepcopy

from osgeo import gdal
import pyproj
import shapely
from affine import Affine

from . import tools
from .. import gdal_tools




class NonIntersectingGeoSeriesError(Exception):
    pass

class Mask(object):
    """Object to manage mask for temds region objects.

    Data is stored internally as a raster with integer values.
    Values are taken mean:
        1: Cells you are interested in.
        0: Other cells
    You may be interested in cells based on if they have available data or not,
    or You may be interested in cells because they are of interest to a project
    you are working on. It pretty arbitrary, but region.Region supports
    using a Mask to set values where the mask is 0 to a no data value.


    """
    def __init__(self, mask: gdal.Dataset):
        """
        """
        self.raster = mask ## raster
        
    @classmethod
    def from_geoseries(cls, mask_series, resolution, extent_gpd = None, align_extent_to_resolution=True):
        """
        Parameters
        ----------
        mask_series: GeoSeries
            GeoSeries representing some valid area of data
        resolution: float 
        extent_gpd: GeoDataframe, Optional
            smaller extent GeoDataframe to clip lager mask to
        align_extent_to_resolution: bool
            if extent_gpd is provided align will align clipping to resolution
            gird
        
        """

        if extent_gpd is None:
            extent_gpd = mask_series
        elif align_extent_to_resolution:
            if not mask_series.intersects(extent_gpd).iloc[0]:
                raise NonIntersectingGeoSeriesError('extent_gpd does not intersect mask_series')

            mask_series = mask_series.intersection(extent_gpd)

            extent_gpd = tools.align_to_resolution(extent_gpd, resolution)
        
        name = 'aoi_mask'
        layer_name = f'{name}_{extent_gpd.crs.to_epsg()}' # For shapefiles, this seems to be the filename
    
        bounds = extent_gpd.bounds.iloc[0]
    
        # Get in memory shape file representation that can be passed to 
        # the rasterization process.
        ds, layer = tools.geopandas_to_ogr_dataset(mask_series, layer_name=layer_name)
    
        opts = gdal.RasterizeOptions(
          format='MEM',
          outputBounds=(bounds['minx'], bounds['miny'], bounds['maxx'], bounds['maxy']),
          xRes=resolution,
          yRes=resolution,
          noData=0,
          burnValues=[1],
          layers=[layer.GetName()],
          outputType=gdal.GDT_Int16
        )
        rds = gdal.Rasterize('', ds, options=opts)


    
        return cls(rds)

    @classmethod
    def from_extent(cls, extent_gpd, resolution, align_extent_to_resolution=True, fill_uniform=False):
        """create mask from extent, all values are set to 1(good)

        Assumes grid resolution is uniform (1000m by 1000m)
        """
        init_boundary = deepcopy(extent_gpd)

        if align_extent_to_resolution:
            extent_gpd = tools.align_to_resolution(extent_gpd, resolution)

        bounds = extent_gpd.bounds.iloc[0]
        rds = gdal_tools.empty_dataset(
            int((bounds['maxx'] - bounds['minx'])//resolution),
            int((bounds['maxy'] - bounds['miny'])//resolution),
            extent_gpd.crs.to_wkt(),
            (bounds['minx'], resolution, 0, bounds['maxy'], 0,  -resolution ),
            1,
            gdal.GDT_Int16
        )  
        as_np = rds.ReadAsArray()
        if fill_uniform:
            as_np[:] = 1
        else:
            as_np[:] = 0
            _,res_x, _, _, _, res_y = rds.GetGeoTransform()
            gt = Affine.from_gdal(*rds.GetGeoTransform())
            for col in range(rds.RasterYSize):
                for row in range(rds.RasterXSize):
                    minx, maxy = gt * (row, col)
                    maxx = minx+res_x
                    miny = maxy+res_y
                    box = shapely.box(minx, miny, maxx, maxy)
                    is_in = init_boundary.iloc[[0]].geometry.intersects(box).values[0]
                    if is_in:
                        as_np[col, row] = 1
        rds.WriteArray(as_np)

        return cls(rds)
    
    @classmethod
    def from_file(cls, where):
        return cls(gdal.Open(where))

    @property
    def resolution(self):
        """tuple because sometimes one res is negative
        """
        return self.transform[1], self.transform[5]
    
    @property
    def transform(self):
        """
        """
        return self.raster.GetGeoTransform()
    
    @property
    def crs(self):
        """
        """
        return pyproj.CRS(self.raster.GetProjection())
    
    @property
    def shape(self):
        return self.raster.RasterXSize, self.raster.RasterYSize

    def to_file(self, where: Path):
        
        # r_aoi = self.as_raster(crs=crs)
        
        # outfolder = Path(output_dir, f"{name}")
        # outfolder.mkdir(parents=True, exist_ok=True)
        
        # crs = pyproj.CRS.from_wkt(self.raster.GetProjection()).to_epsg()
        # resolution = self.raster.GetGeoTransform()[1]
        # outfile_name = Path(outfolder, f"{name}_{crs}_{resolution}m.tiff")
        
        driver = gdal.GetDriverByName('GTiff')
        driver.CreateCopy(str(where), self.raster)


