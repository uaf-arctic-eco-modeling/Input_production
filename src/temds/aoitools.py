#!/usr/bin/env python

import requests
import pathlib
import zipfile
import subprocess
import shutil
import glob

import numpy as np
import geopandas as gpd

from osgeo import gdal

import temds.util



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
    temds.util.mkdir_p(pathlib.Path(self.root, '00-download/mask'))
    with open(pathlib.Path(self.root, '00-download/mask', self.politic_map_fname), 'wb') as new_file:
      new_file.write(r.content)

    r = requests.get(self.eco_map_url)
    temds.util.mkdir_p(pathlib.Path(self.root, '00-download/mask'))
    with open(pathlib.Path(self.root, '00-download/mask', self.eco_map_fname), 'wb') as new_file:
      new_file.write(r.content)

  def _unzip(self):
    '''
    uzips into a directory of the same name as the zip file and right next
    to the zip file.
    '''
    fpath = pathlib.Path(self.root, '00-download/mask', self.politic_map_fname)
    print(f"Extracting {fpath=}")
    with zipfile.ZipFile(fpath, 'r') as zip_ref:
      x = pathlib.Path(fpath.parent, fpath.stem)
      print(f"Extracting {x=}")
      zip_ref.extractall(x)

    fpath = pathlib.Path(self.root, '00-download/mask', self.eco_map_fname)
    print(f"Extracting {fpath=}")
    with zipfile.ZipFile(fpath, 'r') as zip_ref:
      x = pathlib.Path(fpath.parent, fpath.stem)
      print(f"Extracting {x=}")
      zip_ref.extractall(x)

  # def create_from_scratch(self):
  #   self._download()
  #   self._unzip()
  #   self.create_from_shapefiles():

  def create_from_shapefiles(self, trim_to_shape=None):
    self.merge_and_buffer_shapefiles(pathlib.Path(self.root, '00-download/mask', self.politic_map_fname),
                                pathlib.Path(self.root, '00-download/mask', self.eco_map_fname),
                                trim_to_shape=trim_to_shape
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
            self.root + '01-aoi/aoi_5km_buffer_6931/aoi_5km_buffer_6931.shp',
            self.root + '01-aoi/aoi_5km_buffer_6931.tiff'
            ]
    print(args)
    subprocess.run(args)



  def merge_and_buffer_shapefiles(self, global_political_map, eco_region_map, trim_to_shape=None):
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
    trim_to_shape: None or path to shapefile or raster
    

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

    if trim_to_shape:
      from IPython import embed; embed()

      clipping_shape = gpd.read_file(pathlib.Path(self.root, "01-aoi/southcentral_AK_rough/southcentral_AK_rough.shp"))



    #  {01-aoi}/{name}/{name}_{CRS}_{RES}.tif
    # 01-aoi/
    #     full_arctic/
    #         full_arctic_6931_4km.tiff
    #         full_arctic_6931/
    #             full_arctic_6931.shp

    #         full_arctic_4327.tiff
    #         full_arctic_4327/
    #             full_arctic_4327.shp
    
    #     southcentral_AK/
    #         southcentral_AK_6931_4km.tiff
    #         southcentral_AK_6931/
    #             southcentral_AK_6931.shp

    #         southcentral_AK_4327.tiff
    #         southcentral_AK_4327/
    #             southcentral_AK_4327.shp



    temds.util.mkdir_p(self.root + '/aoi_4326/')
    temds.util.mkdir_p(self.root + '/aoi_6931/')
    temds.util.mkdir_p(self.root + '/aoi_5km_buffer_6931/')

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



# in pixels....
TILE_SIZE_X = 100
TILE_SIZE_Y = 100


class TileIndex(object):

  def __init__(self, root):
    self.root = root

    self.aoimask = AOIMask(root=self.root)
    self.aoimask.load_from_raster(pathlib.Path(self.root, '01-aoi/aoi_5km_buffer_6931.tiff'))

  def remove_tiles(self):
    shutil.rmtree(self.root + "/tiles")
  

  def calculate_tile_gridsize(self):

    maskX, maskY = self.aoimask.size()

    N_TILES_X = int(maskX / TILE_SIZE_X)
    N_TILES_Y = int(maskY / TILE_SIZE_Y)

    if maskX % TILE_SIZE_X > 0:
      N_TILES_X += 1

    if maskX % TILE_SIZE_Y > 0:
      N_TILES_Y += 1

    return N_TILES_X, N_TILES_Y


  def calculate_tile_extents(self):
    '''
    Chop a raster up into tiles.
    Returns list of tile extent dictionaries. Each dict will have x, y, minx
    and max (projection coords) and H and V indices in the tileset. And the
    resolution.
    '''

    
    maskX, maskY = self.aoimask.size()

    aoi_extents = self.aoimask.extents()

    aoiGT = self.aoimask.geoTransform()

    N_tiles_X, N_tiles_Y = self.calculate_tile_gridsize()

    tile_extents = []

    for h in range(N_tiles_X):
      for v in range(N_tiles_Y):

        tile_xmin = aoi_extents['minx'] + TILE_SIZE_X * h * aoiGT[1]
        if (h+1) == len(range(N_tiles_X)):
          tile_xmax = tile_xmin + (maskX % TILE_SIZE_X) * aoiGT[1]
        else:
          tile_xmax = tile_xmin + TILE_SIZE_X * aoiGT[1]

        tile_pixelXsize = aoiGT[1]
        tile_pixelYsize = aoiGT[5]

        # Origin LOWER LEFT
        tile_ymin = aoi_extents['miny'] + tile_pixelYsize * maskY \
                    + TILE_SIZE_Y * v * tile_pixelYsize * -1
        if (v+1) == len(range(N_tiles_Y)):
          tile_ymax = tile_ymin + (maskY % TILE_SIZE_Y) * tile_pixelYsize * -1
        else:
          tile_ymax = tile_ymin + TILE_SIZE_Y * tile_pixelYsize * -1 

        # # Origin UPPER LEFT 
        # tile_ymin = aoi_extents['miny'] + TILE_SIZE_Y * v * aoiGT[5]
        # if (v+1) == len(range(N_tiles_Y)):
        #   tile_ymax = tile_ymin + (maskY % TILE_SIZE_Y) * aoiGT[5]
        # else:
        #   tile_ymax = tile_ymin + TILE_SIZE_Y * aoiGT[5]

        tile_extents.append(dict(hidx=h, vidx=v, 
                                 xmin=tile_xmin, xmax=tile_xmax, 
                                 ymin=tile_ymin, ymax=tile_ymax,
                                 xrez=tile_pixelXsize, yrez=tile_pixelYsize))

    return tile_extents    

  def cut_tileset(self, tile_extents):
    '''Given a list of tile extents, call gdal warp and actually crop out
    the tile from the raster.'''

    for tile in tile_extents:

      warpOptions = {
        'format': 'VRT',
        'srcSRS': 'EPSG:6931',
        'dstSRS': 'EPSG:6931',
        'xRes': tile['xrez'],
        'yRes': tile['yrez'],
        #'outputType': '',
        'outputBounds': [tile['xmin'], tile['ymin'], tile['xmax'], tile['ymax']],
        #'resampleAlg': '',
      }

      # Put it in a temporary dataset
      ds = gdal.Warp('', self.root+'/01-aoi/aoi_5km_buffer_6931.tiff', **warpOptions)

      if np.count_nonzero(ds.ReadAsArray()) < 1:
        print("Skip tile!")
      else:
        # get indices of non-zero data. Use theses to further trim down the
        # extents of the tiles.
        valid_y, valid_x = np.nonzero(ds.ReadAsArray())
        transOptions = {
          'format': 'VRT',
          # [left x, top_y, width, height]
          'srcWin': [valid_x.min(), valid_y.min(), 
                    valid_x.max()-valid_x.min()+1, valid_y.max()-valid_y.min()+1 ] 
        }

        print(f"cropping H{tile['hidx']} V{tile['vidx']}", transOptions)
        vrt = gdal.GetDriverByName('VRT')
        ds = gdal.Translate('', ds, **transOptions)

        # This will need updating with respect to location...
        outdir = pathlib.Path(self.root, 'tiles', f"H{tile['hidx']:02d}_V{tile['vidx']:02d}")
        temds.util.mkdir_p(outdir)

        print(f"Writing to: {outdir}")
        out = gdal.GetDriverByName('GTiff')
        out.CreateCopy(pathlib.Path(outdir, "EPSG_6931.tiff"), ds)

        warpOpts = {'dstSRS':'EPSG:4326'}
        ds = gdal.Warp(pathlib.Path(outdir, "EPSG_4326.tiff"), ds, **warpOpts)


  def create_tile_index(self):
    opts = {
      'overwrite': True,
      'filenameFilter' : "*6931.tiff",

    }
    files = glob.glob(self.root + "/tiles/**/EPSG_6931.tiff")

    print(f"Found {len(files)} files to tile.")    
    dstPath = pathlib.Path(self.root, "tile_index.shp")

    gdal.TileIndex(dstPath, 
                   files,
                   **opts)
    if not dstPath.exists():
      raise RuntimeError(f"PROBLEM CREATING TILE INDEX: {dstPath}")
    

  def get_tile_index_total_area(self):
    files = glob.glob(self.root + "/tiles/**/EPSG_6931.tiff")
    total = 0
    for raster_file in files:
      ds = gdal.Open(raster_file,  gdal.gdalconst.GA_ReadOnly)
      total += ds.RasterXSize * ds.RasterYSize

    return total

  def register_tileset():
    '''use gdal.TileIndex()'''
    raise NotImplementedError("Not implemented yet")