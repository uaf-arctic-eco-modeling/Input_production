#!/usr/bin/env python

import requests
import pathlib
import zipfile
import shutil
import glob
import tempfile
import os

import numpy as np
import geopandas as gpd
import pandas as pd

from osgeo import gdal, ogr, osr

import temds.util

gdal.UseExceptions()

def geopandas_to_ogr_dataset(geoseries, layer_name="layer"):
    """Convert GeoPandas GeoSeries to OGR vector dataset (in-memory)

    Parameters
    ----------
    geoseries : geopandas.GeoSeries
        The vector data to convert
    layer_name : str, default "layer"
        Name for the output layer

    Returns
    -------
    ogr.DataSource
        In-memory OGR dataset containing the vector data
    ogr.Layer
        The layer within the dataset
    """

    # Create in-memory vector dataset
    driver = ogr.GetDriverByName('Memory')
    ds = driver.CreateDataSource('')

    # Set up spatial reference
    srs = None
    if geoseries.crs is not None:
        srs = osr.SpatialReference()
        srs.ImportFromWkt(geoseries.crs.to_wkt())

    # Determine geometry type from first geometry
    first_geom = geoseries.iloc[0]
    geom_type_map = {
        'Point': ogr.wkbPoint,
        'LineString': ogr.wkbLineString,
        'Polygon': ogr.wkbPolygon,
        'MultiPoint': ogr.wkbMultiPoint,
        'MultiLineString': ogr.wkbMultiLineString,
        'MultiPolygon': ogr.wkbMultiPolygon,
    }

    geom_type = geom_type_map.get(first_geom.geom_type, ogr.wkbUnknown)

    # Create layer
    layer = ds.CreateLayer(layer_name, srs, geom_type)

    # Add features to layer
    for idx, geom in geoseries.items():
        feature = ogr.Feature(layer.GetLayerDefn())

        # Convert shapely geometry to OGR
        ogr_geom = ogr.CreateGeometryFromWkt(geom.wkt)
        feature.SetGeometry(ogr_geom)

        layer.CreateFeature(feature)
        feature = None  # Clean up reference

    return ds, layer  

def raster_to_polygon(gdal_dataset, output_shapefile_dir=None):
    """Convert gdal.Dataset to polygon(s)"""

    layer_name = 'aoi_polygons'

    # Get the raster band (assuming band 1)
    srcband = gdal_dataset.GetRasterBand(1)

    if not pathlib.Path(output_shapefile_dir).is_dir():
      raise ValueError(f"Output shapefile path is not a directory: {output_shapefile_dir}")

    # if not pathlib.Path(output_shapefile_dir).is_dir():
    #     output_shapefile_dir = pathlib.Path(output_shapefile_dir).with_suffix('')

    # Create output vector dataset
    if output_shapefile_dir:
        # Save to file
        driver = ogr.GetDriverByName("ESRI Shapefile")
        print(output_shapefile_dir)
        dst_ds = driver.Create(output_shapefile_dir, 0, 0, 0, gdal.GDT_Unknown)
    else:
        # In-memory
        driver = ogr.GetDriverByName("Memory")
        dst_ds = driver.CreateDataSource("")


    assert dst_ds is not None, "Failed to create output dataset"
    # Create output layer

    srs = osr.SpatialReference(wkt=gdal_dataset.GetProjection())
    dst_layer = dst_ds.CreateLayer(layer_name, srs=srs)

    # Add a field to store pixel values
    field_defn = ogr.FieldDefn("DN", ogr.OFTInteger)
    dst_layer.CreateField(field_defn)

    # Polygonize
    gdal.Polygonize(srcband, None, dst_layer, 0, [], callback=None)

    del dst_layer
    del dst_ds

    return layer_name

def gdal_dataset_to_geopandas(gdal_dataset, mask_value=1):
    """Convert gdal.Dataset to GeoPandas GeoDataFrame"""

    # Create temporary shapefile
    with tempfile.TemporaryDirectory() as tmp_shapefile_dir:

      try:
          # Polygonize to temporary shapefile
          foo = raster_to_polygon(gdal_dataset, tmp_shapefile_dir)

          # Read with GeoPandas
          gdf = gpd.read_file(pathlib.Path(tmp_shapefile_dir, foo).with_suffix('.shp'))

          # Filter by pixel value if needed
          if mask_value is not None:
              gdf = gdf[gdf['DN'] == mask_value]

          return gdf

      finally:
          # Clean up temp files
          for ext in ['.shp', '.shx', '.dbf', '.prj']:
              try:
                  os.unlink(tmp_shapefile_dir.replace('.shp', ext))
              except Exception:
                  pass



class AOIMask(object):
  '''
  Object that encapsulates an Area of Interest Mask.
  '''
  politic_map_fname = "geoBoundariesCGAZ_ADM1.zip"
  politic_map_url = f"https://github.com/wmgeolab/geoBoundaries/raw/main/releaseData/CGAZ/{politic_map_fname}"
  eco_map_fname = "Ecoregions2017.zip"
  eco_map_url = f"https://storage.googleapis.com/teow2016/{eco_map_fname}"

  RES = 4000 # meters

  def __init__(self):
    # anything to do here?
    self._raster = None
    pass

  @staticmethod
  def download():
    '''
    Go the web and get some stuff...
    '''
    r = requests.get(AOIMask.politic_map_url)
    temds.util.mkdir_p(pathlib.Path('working/00-download/mask'))
    with open(pathlib.Path('working/00-download/mask', AOIMask.politic_map_fname), 'wb') as new_file:
      new_file.write(r.content)

    r = requests.get(AOIMask.eco_map_url)
    temds.util.mkdir_p(pathlib.Path( 'working/00-download/mask'))
    with open(pathlib.Path('working/00-download/mask', AOIMask.eco_map_fname), 'wb') as new_file:
      new_file.write(r.content)

  @staticmethod
  def unzip():
    '''
    uzips into a directory of the same name as the zip file and right next
    to the zip file.
    '''
    fpath = pathlib.Path('working/00-download/mask', AOIMask.politic_map_fname)
    print(f"Extracting {fpath=}")
    with zipfile.ZipFile(fpath, 'r') as zip_ref:
      x = pathlib.Path(fpath.parent, fpath.stem)
      print(f"Extracting {x=}")
      zip_ref.extractall(x)

    fpath = pathlib.Path('working/00-download/mask', AOIMask.eco_map_fname)
    print(f"Extracting {fpath=}")
    with zipfile.ZipFile(fpath, 'r') as zip_ref:
      x = pathlib.Path(fpath.parent, fpath.stem)
      print(f"Extracting {x=}")
      zip_ref.extractall(x)

  @staticmethod
  def from_raw(download=False, unzip=False, trim_to_shape=None):
    '''
    Need a better name for this.
    But it is supposed to make the full AOI mask as per the original means from 
    H.G. work. Makes a circumpolar mask (so above a certain latitude) in 
    the 6931 projection.
    '''

    if download:
      AOIMask.download()
    if unzip:
      AOIMask.unzip()

    aoimask = AOIMask()

    aoimask.create_from_political_and_ecoregion_maps(
      "working/00-download/mask/geoBoundariesCGAZ_ADM1",
      "working/00-download/mask/Ecoregions2017",
      trim_to_shape=trim_to_shape
    )

    assert aoimask.aoi is not None, "AOI not defined yet"
    assert aoimask.aoi.crs is not None, "AOI has no CRS"
    assert aoimask.aoi.crs.to_string() == 'EPSG:6931'

    return aoimask

  @staticmethod
  def load_vector(vector_file):

    instance = AOIMask()

    instance.aoi = gpd.read_file(vector_file).geometry # Make sure we end up with a GeoSeries

    return instance

  @staticmethod
  def load_raster(raster_file):

    gdf = gdal_dataset_to_geopandas(gdal.Open(raster_file,gdal.gdalconst.GA_ReadOnly), mask_value=1)

    dissolved = gdf.dissolve()
    aoi = dissolved.geometry

    instance = AOIMask()

    instance.aoi = aoi

    return instance

  def get_raster_extent(self):
    '''
    Returns a pandas.DataFrame with columns: (minx, miny, maxx, maxy) that
    is the extent of the raster representation of the AOI.
    '''
    assert self.aoi is not None, "AOI not defined yet"

    if not self._raster:
      self._raster = self.as_raster()

   # Get the extent from the extent raster
    gt = self._raster.GetGeoTransform()

    minx = gt[0]
    miny = gt[3]
    maxx = gt[0] + (gt[1] * self._raster.RasterXSize)
    maxy = gt[3] + (gt[5] * self._raster.RasterYSize)

    # Force the image to have miny < maxy
    # (origin in lower left)
    if miny > maxy:
      #print("Flipping image vertically...")
      miny, maxy = maxy, miny

    return pd.DataFrame(dict(minx=minx, miny=miny, maxx=maxx, maxy=maxy), index=[0])

  def get_vector_bounds(self):
    '''
    Returns a pandas DataFrame with columns: (minx, miny, maxx, maxy) that 
    are the extents of the vector representation of the AOI.
    '''
    assert self.aoi is not None, "AOI not defined yet"

    bounds = self.aoi.geometry.bounds

    return bounds

  def get_resolution_aligned_bounds(self):
    '''
    Round the bounds outward to the nearest pixel edge, considering the 
    resolution. Only works for certain projections I think?
    '''
    assert self.aoi.crs is not None, "AOI has no CRS"
    assert self.aoi.crs.to_epsg() == 6931, "AOI must be in EPSG:6931"

    bounds = self.get_vector_bounds()
    #print(f"Bounds before rounding outwards\n {bounds}")

    bounds = np.ceil((bounds/1000))*1000

    max_x = bounds['maxx'] + (self.RES - (bounds['maxx'] - bounds['minx']) % self.RES)
    max_y = bounds['maxy'] + (self.RES - (bounds['maxy'] - bounds['miny']) % self.RES)

    bounds_2 = pd.Series(dict(minx=bounds['minx'].squeeze(),
                miny=bounds['miny'].squeeze(),
                maxx=max_x.squeeze(),
                maxy=max_y.squeeze()))
    #print(f"Bounds after rounding outwards\n {bounds_2}")

    #print(f"Differences in bounds: {bounds_2 - bounds}")

    return bounds_2

  def to_shapefile(self, output_dir, name, crs='6931'):

    if self.aoi.crs.to_epsg() != crs:
      print(f"Converting AOI from {self.aoi.crs.to_epsg()} to {crs}")
      aoi_vector = self.aoi.to_crs(crs)
    else:
      print(f"AOI is already in {crs}")
      aoi_vector = self.aoi

    ## f"{output_dir}/{name}/{name}_{EPSG}/{name}_{EPSG}.shp"
    outfolder = pathlib.Path(output_dir, f"{name}", f"{name}_{aoi_vector.crs.to_epsg()}")
    outfolder.mkdir(parents=True, exist_ok=True)

    outfile_name = pathlib.Path(outfolder,  f"{name}_{aoi_vector.crs.to_epsg()}.shp")
    print(f"Saving shapefile...{outfile_name}")
    aoi_vector.to_file(outfile_name, layer='aoi_mask')

  def to_rasterfile(self, output_dir, name, crs=6931):

    assert self.aoi is not None, "AOI not defined yet; you need an AOI to rasterize!"

    r_aoi = self.as_raster(crs=crs)

    outfolder = pathlib.Path(output_dir, f"{name}")
    outfolder.mkdir(parents=True, exist_ok=True)
    outfile_name = pathlib.Path(outfolder, f"{name}_{crs}_{self.RES}m.tiff")

    driver = gdal.GetDriverByName('GTiff')
    driver.CreateCopy(str(outfile_name), r_aoi)
    print(f"Raster AOI saved to {outfile_name}")

  def raster_size(self):
    assert self.aoi is not None, "AOI not defined yet; you need an AOI geometry to get its size!"
    r_aoi = self.as_raster()
    return (r_aoi.RasterXSize, r_aoi.RasterYSize)

  def as_raster(self, crs=6931, forceUpdate=False):

    assert self.aoi is not None, "AOI not defined yet; you need an AOI geometry to rasterize!"

    if self._raster is not None and not forceUpdate:
      return self._raster

    #log.debug("Computing raster representation of AOI")

    if self.aoi.crs.to_epsg() != crs:
      print(f"Converting AOI from {self.aoi.crs.to_epsg()} to {crs}")
      aoi_vector = self.aoi.to_crs(crs)
    else:
      print(f"AOI is already in {crs}")
      aoi_vector = self.aoi

    if aoi_vector.crs.to_epsg() != 6931:
      raise RuntimeError("Can only rasterize in EPSG:6931 right now.")

    #output_path = pathlib.Path(f"{name}/{name}_{srs}_{resolution}_{xsize}_{ysize}.tiff")
    name = 'aoi_mask'
    layer_name = f'{name}_{crs}' # For shapefiles, this seems to be the filename

    # Might be able to simply use target Aligned pixels (-tap)?
    # although I have some memory of trying -tap option and having it be buggy
    bounds = self.get_resolution_aligned_bounds()

    # Get in memory shape file representation that can be passed to 
    # the rasterization process.
    ds, layer = geopandas_to_ogr_dataset(aoi_vector, layer_name=layer_name)

    opts = gdal.RasterizeOptions(
      format='MEM',
      outputBounds=(bounds['minx'], bounds['miny'], bounds['maxx'], bounds['maxy']),
      xRes=self.RES,
      yRes=self.RES,
      noData=0,
      burnValues=[1],
      layers=[layer.GetName()],
      outputType=gdal.GDT_Int16

    )

    rds = gdal.Rasterize('', ds, options=opts)

    self._raster = rds
    return rds


    # args = ['gdal_rasterize',
    #         '-l', layer_name,
    #         '-burn', str(1),
    #         '-tr', str(self.RES), str(self.RES),
    #         '-a_nodata', str(0),
    #         '-te', f"{bounds['minx']}", f"{bounds['miny']}", f"{bounds['maxx']}", f"{bounds['maxy']}",
    #         '-ot', 'Int16',
    #         '-of', 'GTiff',
    #         f'{output_dir}/{name}/{name}_{crs}/{name}_{crs}.shp',
    #         f'{output_dir}/{name}/{name}_{crs}_{self.RES}m.tiff'
    #         ]
    # print(args)
    # subprocess.run(args)

  def raster_geoTransform(self):
    assert self.aoi is not None, "AOI not defined yet; you need and AOI geometry to get the transform!"
    r_aoi = self.as_raster()
    geotransform = r_aoi.GetGeoTransform()
    return geotransform

  def raster_extents(self):
    assert self.aoi is not None, "AOI not defined yet; you need and AOI geometry to get the extents!"
    r_aoi = self.as_raster()
    geotransform = self.raster_geoTransform()
    minx = geotransform[0]
    miny = geotransform[3]
    maxx = minx + geotransform[1] * r_aoi.RasterXSize
    maxy = miny + geotransform[5] * r_aoi.RasterYSize

    return dict(minx=minx, miny=miny, maxx=maxx, maxy=maxy)

  def create_from_political_and_ecoregion_maps(self, global_political_map, eco_region_map, trim_to_shape=None):
    '''
    Need a better name for this method......
    Creates a vector geometry. This geometry is a geopandas.geoseries.GeoSeries
    which is a polygon of the arctic region, with CRS EPSG:6931. This shape is
    buffered by 5km as the last step.

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

    self.aoi = eco_north.union(ak_greenland, align=True)

    # Convert to EPSG:6931
    self.aoi = self.aoi.to_crs(epsg=6931)

    # Buffer it by 5km. This needs to be done after converting to EPSG:6931
    # so that it gets the southern latitudes correctly 
    self.aoi = self.aoi.buffer(5000)


    if trim_to_shape:
      clipping_shape = gpd.read_file(trim_to_shape)
      clipping_shape = clipping_shape.to_crs(epsg=6931)

      self.aoi = gpd.clip(self.aoi, clipping_shape)

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







# in pixels....
TILE_SIZE_X = 100
TILE_SIZE_Y = 100


class TileIndex(object):

  def __init__(self, root, aoimask):
    self.root = root
    self.aoimask = aoimask

  def remove_tiles(self):
    shutil.rmtree(self.root + "/tiles")


  def calculate_tile_gridsize(self):

    maskX, maskY = self.aoimask.raster_size()

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


    maskX, maskY = self.aoimask.raster_size()

    aoi_extents = self.aoimask.raster_extents()

    aoiGT = self.aoimask.raster_geoTransform()

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

  def cut_tileset(self, tile_extents, nickname=''):
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
      #ds = gdal.Warp('', self.root+'/01-aoi/aoi_5km_buffer_6931.tiff', **warpOptions)
      ds_tile = gdal.Warp('', self.aoimask.as_raster(), **warpOptions)

      if np.count_nonzero(ds_tile.ReadAsArray()) < 1:
        print("Skip tile!")
      else:
        print(f"TIME TO TILE! {tile=}")
        # get indices of non-zero data. Use these to further trim down the
        # extents of the tiles.
        valid_y, valid_x = np.nonzero(ds_tile.ReadAsArray())

        xoffset, px_w, rot1, yoffset, rot2, px_h = ds_tile.GetGeoTransform()

        MINX = px_w * valid_x.min() + rot1 * 0 + xoffset
        MAXX = px_w * (valid_x.max()+1) + rot1 * 0 + xoffset
        MINY = rot2 * 0 + px_h * valid_y.min() + yoffset
        MAXY = rot2 * 0 + px_h * (valid_y.max()+1) + yoffset

        warpOptions2 = {
          'format': 'VRT',
          'srcSRS': 'EPSG:6931',
          'dstSRS': 'EPSG:6931',
          'xRes': tile['xrez'],
          'yRes': tile['yrez'],
          'outputBounds': [MINX, MINY, MAXX, MAXY],
        }
        ds_tile_clipped = gdal.Warp('', ds_tile, **warpOptions2)

        # Tried implementing this with gdal.Translate and using the srcWin
        # option, which uses pixel/line coords, but it seemed kinda buggy
        # for some edge pixels - so gave up and used gdal warp which requried
        # calculating extents in projection coords.


        # This will need updating with respect to location...
        outdir = pathlib.Path(self.root, nickname, 'tiles', f"H{tile['hidx']:02d}_V{tile['vidx']:02d}")
        temds.util.mkdir_p(outdir)

        print(f"Writing to: {outdir}")
        out = gdal.GetDriverByName('GTiff')
        out.CreateCopy(pathlib.Path(outdir, "EPSG_6931.tiff"), ds_tile_clipped)

        # This fails in some small tiles - the warping to a different projection
        # collapses one of the dimensons to zero...
        # warpOpts = {'dstSRS':'EPSG:4326'}
        # _ = gdal.Warp(pathlib.Path(outdir, "EPSG_4326.tiff"), ds_tile_clipped, **warpOpts)



  def create_tile_index(self, nickname='', id=''):
    '''Use gdal.TileIndex() to create a shapefile tile index of the tileset.
    In its present form, this requires the tileset to have been "cut" already,
    meaning that there needs to be a hierarchy of folders containing the tile
    rasters.

    nickname: str 
      A name to identify the tileset. If nickname was used to cut the tileset,
      then you should use the same name here, so that the tile folders can be
      found. Nickname corresponds to the folder name that contains the "tiles/"
      directory.

    id: str
      A unique identifier for the tileset. This can be used to distinguish
      between different tilesets that may have similar names. This is added to
      the tile index shapefile name.

    '''
    opts = {
      'overwrite': True,
      'filenameFilter' : "*6931.tiff",

    }

    pattern = pathlib.Path(self.root, nickname, "tiles/**/EPSG_6931.tiff")
    files = glob.glob(str(pattern))

    if len(files) < 1:
      raise RuntimeError(f"No files found matching {pattern}, can't create tile index.")

    print(f"Found {len(files)} files to tile.")
    dstPath = pathlib.Path(self.root, nickname, f"tile_index{id}.shp")

    gdal.TileIndex(dstPath, 
                   files,
                   **opts)
    if not dstPath.exists():
      raise RuntimeError(f"PROBLEM CREATING TILE INDEX: {dstPath}")
    
    # Add some convenience columns to the shapefile with tile id and 
    # tile H and V indices...

    # Need to read the file in, add a few columns and save it again...
    df = gpd.read_file(dstPath)
    df['tile_id'] = df['location'].str.extract(r'(H\d+_V\d+)')

    # Separate H and V columns:
    df[['H', 'V']] = df['location'].str.extract(r'H(\d+)_V(\d+)')
    df['H'] = df['H'].astype(int)  # Convert to integers
    df['V'] = df['V'].astype(int)

    print(f"Finished adding convenience columns to tile index, saving to {dstPath}")
    df.to_file(dstPath, driver='ESRI Shapefile')


  def get_tile_index_total_area(self, nickname=''):
    '''
    Full area of all the tiles in the tileset. Counting ocean pixels, etc,
    that may be masked later...
    '''
    pattern = pathlib.Path(self.root, nickname, "tiles/**/EPSG_6931.tiff")
    files = glob.glob(str(pattern))
    total = 0
    if len(files) < 1:
      print(f"No files found matching {pattern}")
      raise RuntimeError(f"No files found matching {pattern} for tile index area calculation.")
    for raster_file in files:
      ds = gdal.Open(raster_file,  gdal.gdalconst.GA_ReadOnly)
      total += ds.RasterXSize * ds.RasterYSize

    return total

  def register_tileset():
    '''use gdal.TileIndex()'''
    raise NotImplementedError("Not implemented yet")