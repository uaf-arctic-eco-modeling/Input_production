import numpy as np
import geopandas as gpd
from osgeo import gdal


class AOIMask(object):
  def __init__(self):
    pass
    #self.political_map = 
    #self.ecoregion_map =

  def _download():
    pass

  def _unzip():
    pass

  def create_from_scratch(self):
    self._download()
    self._unzip()
    pass

  def load_from_raster(self, raster_file):
    self.aoi_raster = gdal.Open(raster_file,  gdal.gdalconst.GA_ReadOnly)

  def load_from_vector(self, vector_file):
    self.aoi_vector = gpd.read_file(vector_file)


  def geoTransform(self):
    geotransform = self.aoi_raster.GetGeoTransform()
    return geotransform

  def extents(self):
    '''
    maybe extents is for raster files?
    returns dict with keys (minx, miny, maxx, maxy)
    '''
    geoTransform = self.aoi_raster.GetGeoTransform()
    minx = geoTransform[0]
    miny = geoTransform[3]
    maxx = minx + geoTransform[1] * self.aoi_raster.RasterXSize
    maxy = miny + geoTransform[5] * self.aoi_raster.RasterYSize

    return dict(minx=minx, miny=miny, maxx=maxx, maxy=maxy)


  def bounds(self):
    '''
    maybe bounds is for vectors?
    WARNING! THIS ONE AND THE RASTER VERSION HAVE miny, maxy REVERSED!!
    ONE IS BOTTOM UP THE OTHER IS TOP DOWN CONFIRM!!!!
    returns dict with keys (minx, miny, maxx, maxy)
    '''
    RES = 4000

    bounds = self.aoi_vector.geometry.bounds

    # Funky business to get nice clean numbers for the bounds that are big enough.
    # Extents is a DataFrame, so we can proccess it en masse.
    # numbers start like this:
    #
    #                minx          miny          maxx          maxy
    #     0 -4.602688e+06 -3.485976e+06  4.363719e+06  4.247969e+06
    #
    # and end like this:
    #
    #             minx       miny       maxx       maxy
    #     0 -4602000.0 -3485000.0  4364000.0  4248000.0
    #
    # actually not sure this works as intended for negative numbers??
    bounds = np.ceil((bounds/1000))*1000

    max_x = bounds['maxx'] + (RES - (bounds['maxx'] - bounds['minx']) % RES)
    max_y = bounds['maxy'] + (RES - (bounds['maxy'] - bounds['miny']) % RES)


    # The above data structures are all pandas.DataFrames so you gotta get just
    # the values out.
    return dict(minx=bounds['minx'].values[0],
                miny=bounds['miny'].values[0],
                maxx=max_x.values[0],
                maxy=max_y.values[0])











  def size(self):
    return self.aoi_raster.RasterXSize, self.aoi_raster.RasterYSize


  def save_rasterize(self):
    pass

  def save_vector(self):
    pass