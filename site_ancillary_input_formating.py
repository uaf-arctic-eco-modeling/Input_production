
import os
import pandas as pd
import rasterio
import geopandas as gpd
import xarray as xr
import gzip
import numpy as np
import matplotlib.pyplot as plt
import shutil



### path to the directory that will store the final netcdf input files
indir = '/Users/helenegenet/Helene/TEM/INPUT/calibration_input'
### path to the directory that stores the CO2 time series
co2dir = '/Users/helenegenet/Helene/TEM/INPUT/production/co2_timeseries'


### site specific ancillary information
# site name
site = 'test'
# coordinates in degree (WGS 1984)
site_lat = 	61.3079
site_lon = -121.2992
# coordinates in m --> refer to this website for easy conversion: https://epsg.io/transform#s_srs=4326&t_srs=3338&x=NaN&y=NaN
x = 1676087.569679508
y = 1679770.1119726289
# soil texture information in %
sand = 91
silt = 5
clay = 4
# community class number
veg_class = 1
# drainage class number
drain_class = 0
# fire return interval (optional), with associated mean severity, mean day of burn and mean area burned
fri_yrs = 2000
fri_severity = 0
fri_jday_of_burn = 0
fri_area_of_burn = 0
# tropographic information (optional - not used for eq runs): elevation in m, slope and aspect in degree
elevation = 0
slope = 0
aspect = 0


### Create the site specific input directory
os.mkdir(os.path.join(indir,site))


### Create coordinate value and vector
coords = [site_lon, site_lat]
X = 0
Y = 0



### CO2 file
shutil.copyfile(os.path.join(co2dir,'co2.nc'), os.path.join(indir,site,'co2.nc'))


### Climate data
### This would be a separate procedure - contact H. Genet for details


### Topographic data

topo = pd.DataFrame()
topo['Y'] = [int(Y)]
topo['X'] = [int(X)]
topo['aspect'] = aspect
topo['elevation'] = elevation
topo['slope'] = slope
topo_nc = topo.set_index(['Y', 'X']).to_xarray()
topo_nc['y']=(['Y'],  np.array([float(y)]))
topo_nc['x']=(['X'],  np.array([float(x)]))
topo_nc['lat'] = (['Y','X'],  np.array([[site_lat]]))
topo_nc['lon'] = (['Y','X'],  np.array([[site_lon]]))

topo_nc['lat'].attrs={'standard_name':'latitude','units':'degree_north'}
topo_nc['lon'].attrs={'standard_name':'longitude','units':'degree_east'}
topo_nc['y'].attrs={'standard_name':'projection_y_coordinate','long_name':'y coordinate of projection','units':'m'}
topo_nc['x'].attrs={'standard_name':'projection_x_coordinate','long_name':'x coordinate of projection','units':'m'}
topo_nc['aspect'].attrs={'standard_name':'aspect','units':'degree','grid_mapping':'albers_conical_equal_area','_FillValue': -999.0}
topo_nc['elevation'].attrs={'standard_name':'elevation','units':'m','grid_mapping':'albers_conical_equal_area','_FillValue': -999.0}
topo_nc['slope'].attrs={'standard_name':'slope','units':'degree','grid_mapping':'albers_conical_equal_area','_FillValue': -999.0}

topo_nc.to_netcdf(os.path.join(indir,site,'topo.nc'),unlimited_dims='time')



### Soil texture data

text = pd.DataFrame()
text['Y'] = [int(Y)]
text['X'] = [int(X)]
text['pct_sand'] = sand
text['pct_clay'] = clay
text['pct_silt'] = (1-sand-clay)
text_nc = text.set_index(['Y', 'X']).to_xarray()
text_nc['y']=(['Y'],  np.array([float(y)]))
text_nc['x']=(['X'],  np.array([float(x)]))
text_nc['lat'] = (['Y','X'],  np.array([[site_lat]]))
text_nc['lon'] = (['Y','X'],  np.array([[site_lon]]))

text_nc['lat'].attrs={'standard_name':'latitude','units':'degree_north'}
text_nc['lon'].attrs={'standard_name':'longitude','units':'degree_east'}
text_nc['y'].attrs={'standard_name':'projection_y_coordinate','long_name':'y coordinate of projection','units':'m'}
text_nc['x'].attrs={'standard_name':'projection_x_coordinate','long_name':'x coordinate of projection','units':'m'}
text_nc['pct_sand'].attrs={'standard_name':'sand','units':'pct','grid_mapping':'albers_conical_equal_area','_FillValue': -999.0}
text_nc['pct_silt'].attrs={'standard_name':'silt','units':'pct','grid_mapping':'albers_conical_equal_area','_FillValue': -999.0}
text_nc['pct_clay'].attrs={'standard_name':'clay','units':'pct','grid_mapping':'albers_conical_equal_area','_FillValue': -999.0}

text_nc.to_netcdf(os.path.join(indir,site,'soil-texture.nc'),unlimited_dims='time')





### FRI data

fri = pd.DataFrame()
fri['Y'] = [int(Y)]
fri['X'] = [int(X)]
fri['fri'] = fri_yrs
fri['fri_severity'] = fri_severity
fri['fri_jday_of_burn'] = fri_jday_of_burn
fri['fri_area_of_burn'] = fri_area_of_burn
fri_nc = fri.set_index(['Y', 'X']).to_xarray()
fri_nc['y']=(['Y'],  np.array([float(y)]))
fri_nc['x']=(['X'],  np.array([float(x)]))
fri_nc['lat'] = (['Y','X'],  np.array([[site_lat]]))
fri_nc['lon'] = (['Y','X'],  np.array([[site_lon]]))

fri_nc['lat'].attrs={'standard_name':'latitude','units':'degree_north'}
fri_nc['lon'].attrs={'standard_name':'longitude','units':'degree_east'}
fri_nc['y'].attrs={'standard_name':'projection_y_coordinate','long_name':'y coordinate of projection','units':'m'}
fri_nc['x'].attrs={'standard_name':'projection_x_coordinate','long_name':'x coordinate of projection','units':'m'}
fri_nc['fri'].attrs={'standard_name':'fire_return_interval','units':'yrs','grid_mapping':'albers_conical_equal_area','_FillValue': -999.0}
fri_nc['fri_jday_of_burn'].attrs={'standard_name':'fri_jday_of_burn','units':'doy','grid_mapping':'albers_conical_equal_area','_FillValue': -999.0}
fri_nc['fri_area_of_burn'].attrs={'standard_name':'fri_area_of_burn','units':'','grid_mapping':'albers_conical_equal_area','_FillValue': -999.0}

fri_nc.to_netcdf(os.path.join(indir,site,'fri-fire.nc'),unlimited_dims='time')





### vegetation data

veg = pd.DataFrame()
veg['Y'] = [int(Y)]
veg['X'] = [int(X)]
veg['veg_class'] = veg_class
veg_nc = veg.set_index(['Y', 'X']).to_xarray()
veg_nc['y']=(['Y'],  np.array([float(y)]))
veg_nc['x']=(['X'],  np.array([float(x)]))
veg_nc['lat'] = (['Y','X'],  np.array([[site_lat]]))
veg_nc['lon'] = (['Y','X'],  np.array([[site_lon]]))

veg_nc['lat'].attrs={'standard_name':'latitude','units':'degree_north'}
veg_nc['lon'].attrs={'standard_name':'longitude','units':'degree_east'}
veg_nc['y'].attrs={'standard_name':'projection_y_coordinate','long_name':'y coordinate of projection','units':'m'}
veg_nc['x'].attrs={'standard_name':'projection_x_coordinate','long_name':'x coordinate of projection','units':'m'}
veg_nc['veg_class'].attrs={'standard_name':'veg_class','units':'yrs','grid_mapping':'albers_conical_equal_area','_FillValue': -999.0}

veg_nc.to_netcdf(os.path.join(indir,site,'vegetation.nc'),unlimited_dims='time')





### drainage data

drain = pd.DataFrame()
drain['Y'] = [int(Y)]
drain['X'] = [int(X)]
drain['drainage_class'] = drain_class
drain_nc = drain.set_index(['Y', 'X']).to_xarray()
drain_nc['y']=(['Y'],  np.array([float(y)]))
drain_nc['x']=(['X'],  np.array([float(x)]))
drain_nc['lat'] = (['Y','X'],  np.array([[site_lat]]))
drain_nc['lon'] = (['Y','X'],  np.array([[site_lon]]))

drain_nc['lat'].attrs={'standard_name':'latitude','units':'degree_north'}
drain_nc['lon'].attrs={'standard_name':'longitude','units':'degree_east'}
drain_nc['y'].attrs={'standard_name':'projection_y_coordinate','long_name':'y coordinate of projection','units':'m'}
drain_nc['x'].attrs={'standard_name':'projection_x_coordinate','long_name':'x coordinate of projection','units':'m'}
drain_nc['drainage_class'].attrs={'standard_name':'drainage_class','units':'yrs','grid_mapping':'albers_conical_equal_area','_FillValue': -999.0}

drain_nc.to_netcdf(os.path.join(indir,site,'drainage.nc'),unlimited_dims='time')








