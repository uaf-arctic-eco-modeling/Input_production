
# Author: Helene Genet, hgenet@alaska.edu
# Description: This script produce input data for a specific site, 
# extracting from the tiled input dataset, 
# and overwriting data with observations when available.



import subprocess
import os
import numpy as np
import xarray as xr
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

tilemap = '/Volumes/5TIV/PROCESSED/TILEMAP2_0/tilemap.shp'
indir = '/Volumes/5TIV/PROCESSED/TILES2_0_out'
siteoutdir = '/Users/helenegenet/Helene/TEM/INPUT/production/site_extract'


##### SITE INFORMATION #####

siteinfo = {}
siteinfo = {
    "site": "Siikaneva",
    "lat": 61.83265,
    "lon": 24.19285,
    "sand": 48,
    "silt": 41,
    "clay": 11,
    "vegetation": 80,
    "drainage": 1,
    "fireyear": 1960,
    "fireday": 182,
    "fireseverity": 3,
    "firearea": 600,
    "elev": 164,
    "slope": None,
    "aspect": None,
    "tpi": None 
}






#### FIND THE TILE IN WHICH THE SITE IS LOCATED IN

### Read in the tile shapefile
gdf1 = gpd.read_file(tilemap)

### Read and transform the site coordinates
sitepoint = pd.DataFrame(np.array([[siteinfo['site'], float(siteinfo['lon']), float(siteinfo['lat'])]]), columns=['sitename','lon','lat'])
geometry = [Point(xy) for xy in zip(sitepoint['lon'], sitepoint['lat'])]
gdf2 = gpd.GeoDataFrame(sitepoint, geometry=geometry)
gdf2.set_crs("EPSG:4326", inplace=True)
gdf2 = gdf2.to_crs(gdf1.crs)

### Select the tile overlaping the site
tilename = gdf1.iloc[gdf1.distance(gdf2.geometry.iloc[0]).idxmin()]['tile']
tilename




#### FIND THE PIXEL OVERLAYING THE SITE

### Create a directory for site inputs
if not os.path.exists(os.path.join(siteoutdir,siteinfo['site'])):
  os.makedirs(os.path.join(siteoutdir,siteinfo['site']))

for fn in os.listdir(os.path.join(indir,tilename)):
  print(fn)
  ds = xr.open_dataset(os.path.join(indir,tilename,fn))
  if 'X' in list(ds.coords.keys()):
    subprocess.run("ncks -O -h -d Y," + str(gdf2.geometry[0].y) + " -d X," + str(gdf2.geometry[0].x) + " " + os.path.join(indir,tilename,fn) + " " + os.path.join(siteoutdir,siteinfo['site'],fn), shell=True, capture_output=True, text=True)
  else:
    subprocess.run("cp " + os.path.join(indir,tilename,fn) + " " + os.path.join(siteoutdir,siteinfo['site'],fn), shell=True, capture_output=True, text=True)




##### FORCING OBSERVATIONS

if (siteinfo['sand'] is None) & (siteinfo['silt'] is None) & (siteinfo['clay'] is None):
  print('empty texture')
else:
  txt = xr.open_dataset(os.path.join(siteoutdir,siteinfo['site'],'soil-texture.nc'))
  txt = txt.drop_vars('lambert_azimuthal_equal_area')
  txt = txt.drop_encoding()
  if not siteinfo['sand'] is None:
    txt['pct_sand'].loc[dict(X= txt['X'].values[0], Y= txt['Y'].values[0])] = float(siteinfo['sand'])
    txt['pct_sand'].attrs={'standard_name':'sand','units':'pct','grid_mapping':'albers_conical_equal_area','_FillValue': -999}
  if not siteinfo['silt'] is None:
    txt['pct_silt'].loc[dict(X= txt['X'].values[0], Y= txt['Y'].values[0])] = float(siteinfo['silt'])
    txt['pct_silt'].attrs={'standard_name':'silt','units':'pct','grid_mapping':'albers_conical_equal_area','_FillValue': -999}
  if not siteinfo['clay'] is None:
    txt['pct_clay'].loc[dict(X= txt['X'].values[0], Y= txt['Y'].values[0])] = float(siteinfo['clay'])
    txt['pct_clay'].attrs={'standard_name':'clay','units':'pct','grid_mapping':'albers_conical_equal_area','_FillValue': -999}
  txt['lat'].attrs={'standard_name':'latitude','units':'degree_north','_FillValue': 1.e+20}
  txt['lon'].attrs={'standard_name':'longitude','units':'degree_east','_FillValue': 1.e+20}
  txt['Y'].attrs={'standard_name':'projection_y_coordinate','long_name':'y coordinate of projection','units':'m','_FillValue': 1.e+20}
  txt['X'].attrs={'standard_name':'projection_x_coordinate','long_name':'x coordinate of projection','units':'m','_FillValue': 1.e+20}
  txt.to_netcdf(os.path.join(siteoutdir,siteinfo['site'],'soil-texture.nc'))


if (siteinfo['vegetation'] is None) :
  print('empty vegetation')
else:
  veg = xr.open_dataset(os.path.join(siteoutdir,siteinfo['site'],'vegetation.nc'))
  veg = veg.drop_vars('lambert_azimuthal_equal_area')
  veg = veg.drop_encoding()
  veg['veg_class'].loc[dict(X= veg['X'].values[0], Y= veg['Y'].values[0])] = int(siteinfo['vegetation'])
  veg['veg_class'].attrs={'standard_name':'veg_class','units':'yrs','grid_mapping':'albers_conical_equal_area','_FillValue': -999}
  veg['lat'].attrs={'standard_name':'latitude','units':'degree_north','_FillValue': 1.e+20}
  veg['lon'].attrs={'standard_name':'longitude','units':'degree_east','_FillValue': 1.e+20}
  veg['Y'].attrs={'standard_name':'projection_y_coordinate','long_name':'y coordinate of projection','units':'m','_FillValue': 1.e+20}
  veg['X'].attrs={'standard_name':'projection_x_coordinate','long_name':'x coordinate of projection','units':'m','_FillValue': 1.e+20}
  veg.to_netcdf(os.path.join(siteoutdir,siteinfo['site'],'vegetation.nc'))

if (siteinfo['drainage'] is None) :
  print('empty drainage')
else:
  drain = xr.open_dataset(os.path.join(siteoutdir,siteinfo['site'],'drainage.nc'))
  drain = drain.drop_vars('lambert_azimuthal_equal_area')
  drain = drain.drop_encoding()
  drain['drainage_class'].loc[dict(X= drain['X'].values[0], Y= drain['Y'].values[0])] = int(siteinfo['drainage'])
  drain['drainage_class'].attrs={'standard_name':'drainage_class','units':'yrs','grid_mapping':'albers_conical_equal_area','_FillValue': -999}
  drain['lat'].attrs={'standard_name':'latitude','units':'degree_north','_FillValue': 1.e+20}
  drain['lon'].attrs={'standard_name':'longitude','units':'degree_east','_FillValue': 1.e+20}
  drain['Y'].attrs={'standard_name':'projection_y_coordinate','long_name':'y coordinate of projection','units':'m','_FillValue': 1.e+20}
  drain['X'].attrs={'standard_name':'projection_x_coordinate','long_name':'x coordinate of projection','units':'m','_FillValue': 1.e+20}
  drain.to_netcdf(os.path.join(siteoutdir,siteinfo['site'],'drainage.nc'))

if (siteinfo['elev'] is None) & (siteinfo['aspect'] is None) & (siteinfo['slope'] is None) & (siteinfo['tpi'] is None):
  print('empty texture')
else:
  topo = xr.open_dataset(os.path.join(siteoutdir,siteinfo['site'],'topo.nc'))
  topo = topo.drop_vars('lambert_azimuthal_equal_area')
  topo = topo.drop_encoding()
  if not siteinfo['elev'] is None:
    topo['elevation'].loc[dict(X= topo['X'].values[0], Y= topo['Y'].values[0])] = float(siteinfo['elev'])
  if not siteinfo['slope'] is None:
    topo['slope'].loc[dict(X= topo['X'].values[0], Y= topo['Y'].values[0])] = float(siteinfo['slope'])
  if not siteinfo['aspect'] is None:
    topo['aspect'].loc[dict(X= topo['X'].values[0], Y= topo['Y'].values[0])] = float(siteinfo['aspect'])
  if not siteinfo['tpi'] is None:
    topo['tpi'].loc[dict(X= topo['X'].values[0], Y= topo['Y'].values[0])] = float(siteinfo['tpi'])
  topo['elevation'].attrs={'standard_name':'elevation','units':'m','grid_mapping':'albers_conical_equal_area','_FillValue': -999.0}
  topo['tpi'].attrs={'standard_name':'tpi','units':'','grid_mapping':'albers_conical_equal_area','_FillValue': -999.0}
  topo['aspect'].attrs={'standard_name':'aspect','units':'degree','grid_mapping':'albers_conical_equal_area','_FillValue': -999.0}
  topo['slope'].attrs={'standard_name':'slope','units':'degree','grid_mapping':'albers_conical_equal_area','_FillValue': -999.0}
  topo['lat'].attrs={'standard_name':'latitude','units':'degree_north','_FillValue': 1.e+20}
  topo['lon'].attrs={'standard_name':'longitude','units':'degree_east','_FillValue': 1.e+20}
  topo['Y'].attrs={'standard_name':'projection_y_coordinate','long_name':'y coordinate of projection','units':'m','_FillValue': 1.e+20}
  topo['X'].attrs={'standard_name':'projection_x_coordinate','long_name':'x coordinate of projection','units':'m','_FillValue': 1.e+20}
  topo.to_netcdf(os.path.join(siteoutdir,siteinfo['site'],'topo.nc'))

if (siteinfo['fireyear'] is None) & (siteinfo['fireday'] is None) & (siteinfo['fireseverity'] is None) & (siteinfo['firearea'] is None):
  print('No fire information')
else:
fire = xr.open_dataset(os.path.join(siteoutdir,siteinfo['site'],'historic-explicit-no-fire.nc'))
#fire = fire.drop_vars('lambert_azimuthal_equal_area')
fire = fire.drop_encoding()
fire['time'] = fire.indexes['time'].to_datetimeindex()
if not siteinfo['fireday'] is None:
  fire['exp_jday_of_burn'].loc[dict(X= fire['X'].values[0], Y= fire['Y'].values[0], time= fire['time'].values[(siteinfo['fireyear']-1901)])] = int(siteinfo['fireday'])
  fire['exp_burn_mask'].loc[dict(X= fire['X'].values[0], Y= fire['Y'].values[0], time= fire['time'].values[(siteinfo['fireyear']-1901)])] = 1
if not siteinfo['firearea'] is None:
  fire['exp_area_of_burn'].loc[dict(X= fire['X'].values[0], Y= fire['Y'].values[0], time= fire['time'].values[(siteinfo['fireyear']-1901)])] = int(siteinfo['firearea'])
if not siteinfo['fireseverity'] is None:
  fire['exp_fire_severity'].loc[dict(X= fire['X'].values[0], Y= fire['Y'].values[0], time= fire['time'].values[(siteinfo['fireyear']-1901)])] = int(siteinfo['fireseverity'])
fire['lat'].attrs={'standard_name':'latitude','units':'degree_north','_FillValue': 1.e+20}
fire['lon'].attrs={'standard_name':'longitude','units':'degree_east','_FillValue': 1.e+20}
fire['Y'].attrs={'standard_name':'projection_y_coordinate','long_name':'y coordinate of projection','units':'m','_FillValue': 1.e+20}
fire['X'].attrs={'standard_name':'projection_x_coordinate','long_name':'x coordinate of projection','units':'m','_FillValue': 1.e+20}
fire['exp_burn_mask'].attrs={'standard_name':'exp_burn_mask','units':'','grid_mapping':'albers_conical_equal_area','_FillValue': -999.0}
fire['exp_jday_of_burn'].attrs={'standard_name':'exp_jday_of_burn','units':'doy','grid_mapping':'albers_conical_equal_area','_FillValue': -999.0}
fire['exp_fire_severity'].attrs={'standard_name':'exp_fire_severity','units':'','grid_mapping':'albers_conical_equal_area','_FillValue': -999.0}
fire['exp_area_of_burn'].attrs={'standard_name':'exp_area_of_burn','units':'km2','grid_mapping':'albers_conical_equal_area','_FillValue': -999.0}
fire['time'].attrs.clear()
fire.time.encoding['units'] = 'days since 1901-01-01 00:00:00'
fire.time.encoding['calendar'] = '365_day'
fire.time.attrs['long_name'] = 'time'
fire.time.encoding['_FillValue'] = -999
fire.to_netcdf(os.path.join(siteoutdir,siteinfo['site'],'historic-explicit-fire.nc'))
