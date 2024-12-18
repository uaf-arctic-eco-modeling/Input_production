#!/usr/bin/env python

import pathlib
import requests
import zipfile

import geopandas as gpd

import util

def unzip_AOI_maps():
  fpath = pathlib.Path('working/download/mask/geoBoundariesCGAZ_ADM1.zip')
  print(f"Extracting {fpath=}")
  with zipfile.ZipFile(fpath, 'r') as zip_ref:
    x = pathlib.Path(fpath.parent, fpath.stem)
    print(f"Extracting {x=}")
    zip_ref.extractall(x)

  fpath = pathlib.Path('working/download/mask/Ecoregions2017.zip')
  print(f"Extracting {fpath=}")
  with zipfile.ZipFile(fpath, 'r') as zip_ref:
    x = pathlib.Path(fpath.parent, fpath.stem)
    print(f"Extracting {x=}")
    zip_ref.extractall(x)


def download_AOI_maps():
  fname = 'geoBoundariesCGAZ_ADM1.zip'
  url = f'https://github.com/wmgeolab/geoBoundaries/raw/main/releaseData/CGAZ/{fname}'
  r = requests.get(url)
  util.mkdir_p('working/download/mask/')
  with open(f'working/download/mask/{fname}', 'wb') as new_file:
    new_file.write(r.content)

  fname = 'Ecoregions2017.zip'
  url = f'https://storage.googleapis.com/teow2016/{fname}'
  r = requests.get(url)
  util.mkdir_p('working/download/mask/')
  with open(f'working/download/mask/{fname}', 'wb') as new_file:
    new_file.write(r.content)



def create_AOI_shapefiles(global_political_map, eco_region_map):

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

  util.mkdir_p('working/aoi_4326/')
  util.mkdir_p('working/aoi_6931/')

  AOI.to_crs(4326).to_file('working/aoi_4326/aoi_4326.shp')
  AOI.to_crs(6931).to_file('working/aoi_6931/aoi_6931.shp')


