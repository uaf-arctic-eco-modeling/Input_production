"""
"""
from pathlib import Path

from osgeo import gdal
import pyproj

from . import tools



class Mask(object):
    def __init__(self, mask):
        self.raster = mask ## raster
        
    @classmethod
    def from_geoseries(cls, mask_series, resolution, extent_gpd = None):

        if extent_gpd is None:
            extent_gpd = mask_series
        
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

    @property
    def resolution(self):
        """tuple because sometimes one res is negative
        """
        return self.raster.GetGeoTransform()[1], self.raster.GetGeoTransform()[5]
    

    def to_file(self, where: Path):
        
        # r_aoi = self.as_raster(crs=crs)
        
        # outfolder = Path(output_dir, f"{name}")
        # outfolder.mkdir(parents=True, exist_ok=True)
        
        # crs = pyproj.CRS.from_wkt(self.raster.GetProjection()).to_epsg()
        # resolution = self.raster.GetGeoTransform()[1]
        # outfile_name = Path(outfolder, f"{name}_{crs}_{resolution}m.tiff")
        
        driver = gdal.GetDriverByName('GTiff')
        driver.CreateCopy(str(where), self.raster)


