#!/usr/bin/env python

import requests
import pathlib
import zipfile
import subprocess


import numpy as np
import geopandas as gpd
from osgeo import gdal

import util


class AOIMask(object):
  '''
  Object that encapsulates an Area of Interest Mask.
  '''
  def __init__(self, root):
    self.politic_map_fname = "geoBoundariesCGAZ_ADM1.zip"
    self.politic_map_url = f"https://github.com/wmgeolab/geoBoundaries/raw/main/releaseData/CGAZ/{self.politic_map_fname}"
    self.eco_map_fname = "Ecoregions2017.zip"
    self.eco_map_url = f"https://storage.googleapis.com/teow2016/{self.eco_map_fname}"

    self.root = root
    self.RES = 4000 # meters



  def _download(self):
    '''
    Go the web and get some stuff...
    '''
    r = requests.get(self.politic_map_url)
    util.mkdir_p(pathlib.Path(self.root, 'download/mask'))
    with open(pathlib.Path(self.root, 'download/mask', self.politic_map_fname), 'wb') as new_file:
      new_file.write(r.content)

    r = requests.get(self.eco_map_url)
    util.mkdir_p(pathlib.Path(self.root, 'download/mask'))
    with open(pathlib.Path(self.root, 'download/mask', self.eco_map_fname), 'wb') as new_file:
      new_file.write(r.content)

  def _unzip(self):
    '''
    uzips into a directory of the same name as the zip file and right next
    to the zip file.
    '''
    fpath = pathlib.Path(self.root, 'download/mask', self.politic_map_fname)
    print(f"Extracting {fpath=}")
    with zipfile.ZipFile(fpath, 'r') as zip_ref:
      x = pathlib.Path(fpath.parent, fpath.stem)
      print(f"Extracting {x=}")
      zip_ref.extractall(x)

    fpath = pathlib.Path(self.root, 'download/mask', self.eco_map_fname)
    print(f"Extracting {fpath=}")
    with zipfile.ZipFile(fpath, 'r') as zip_ref:
      x = pathlib.Path(fpath.parent, fpath.stem)
      print(f"Extracting {x=}")
      zip_ref.extractall(x)

  # def create_from_scratch(self):
  #   self._download()
  #   self._unzip()
  #   self.create_from_shapefiles():

  def create_from_shapefiles(self):
    self.merge_and_buffer_shapefiles(pathlib.Path(self.root, 'download/mask', self.politic_map_fname),
                                pathlib.Path(self.root, 'download/mask', self.eco_map_fname),
                              )

  def load_from_raster(self, raster_file):
    self.aoi_raster = gdal.Open(raster_file,  gdal.gdalconst.GA_ReadOnly)
    if self.aoi_raster is None:
      raise RuntimeError(f"Can't open file: {raster_file}")

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

  def get_shapefile_bounds(self):
    '''
    maybe bounds is for vectors?
    WARNING! THIS ONE AND THE RASTER VERSION HAVE miny, maxy REVERSED!!
    ONE IS BOTTOM UP THE OTHER IS TOP DOWN CONFIRM!!!!
    returns dict with keys (minx, miny, maxx, maxy)
    '''

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

    max_x = bounds['maxx'] + (self.RES - (bounds['maxx'] - bounds['minx']) % self.RES)
    max_y = bounds['maxy'] + (self.RES - (bounds['maxy'] - bounds['miny']) % self.RES)


    # The above data structures are all pandas.DataFrames so you gotta get just
    # the values out.
    return dict(minx=bounds['minx'].values[0],
                miny=bounds['miny'].values[0],
                maxx=max_x.values[0],
                maxy=max_y.values[0])


  def rasterize_AOI(self):

    layer_name = 'aoi_5km_buffer_6931'

    bnds = self.get_shapefile_bounds()

    args = ['gdal_rasterize',
            '-l', layer_name,
            '-burn', str(1),
            '-tr', str(self.RES), str(self.RES),
            '-a_nodata', str(0),
            '-te', f"{bnds['minx']}", f"{bnds['miny']}", f"{bnds['maxx']}", f"{bnds['maxy']}",
            '-ot', 'Int16',
            '-of', 'GTiff',
            self.root + '/aoi_5km_buffer_6931/aoi_5km_buffer_6931.shp',
            self.root + '/aoi_5km_buffer_6931.tiff'
            ]
    print(args)
    subprocess.run(args)



  def merge_and_buffer_shapefiles(self, global_political_map, eco_region_map):
    '''
    Creates two shape files in different projections that cover the whole
    area of interest. Each file is a single feature (not sure if this is the
    right term?) with a bunch of polygons defining the outline of the AOI.

    Writes various files to disk. 

    Parameters
    ==========
    global_political_map : str
        path to the global political shapefile
    eco_region_map: str
        path to the eco regeion shapefile
    outdir: str
        path to where the files will be written

    Returns
    ========
    None
    '''
    # Read the eco region shape file, extract the shapes of interest, and then
    # merge (dissolve) them into one single shape (polygon?)
    print(f"Opening {eco_region_map=}...")
    erm = gpd.read_file(eco_region_map)

    eco_tundra = erm[(erm['BIOME_NAME'] == 'Tundra') | (erm['BIOME_NAME'] == 'Boreal Forests/Taiga')]
    eco_north = eco_tundra[(eco_tundra['REALM'] != 'Antarctica') & (eco_tundra['REALM'] != 'Australasia')]

    # Dissolve geometries within `groupby` into single observation
    eco_north = eco_north.dissolve() 

    # Read the global map, 
    print(f"Opening {global_political_map=}...")
    gpm = gpd.read_file(global_political_map)
    ak_greenland = gpm[(gpm['shapeName']=='Alaska') | (gpm['shapeGroup']=='GRL')]
    ak_greenland = ak_greenland.dissolve()
    ak_greenland.to_crs(eco_north.crs)

    AOI = eco_north.union(ak_greenland, align=True)

    util.mkdir_p(self.root + '/aoi_4326/')
    util.mkdir_p(self.root + '/aoi_6931/')
    util.mkdir_p(self.root + '/aoi_5km_buffer_6931/')

    print("Writing AOI files...")
    AOI.to_crs(4326).to_file(self.root + '/aoi_4326/aoi_4326.shp')
    AOI.to_crs(6931).to_file(self.root + '/aoi_6931/aoi_6931.shp')

    AOI_5km_buffer = AOI.to_crs(6931).buffer(5000) # 5km
    AOI_5km_buffer.tmp = 1 # ?? what is this for?
    print("Writing buffered AOI file...")
    AOI_5km_buffer.to_file(self.root + '/aoi_5km_buffer_6931/aoi_5km_buffer_6931.shp')





  def size(self):
    '''Return (width, height).'''
    return self.aoi_raster.RasterXSize, self.aoi_raster.RasterYSize


  def save_rasterize(self):
    pass

  def save_vector(self):
    pass
