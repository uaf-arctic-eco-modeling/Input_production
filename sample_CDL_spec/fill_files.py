#!/usr/bin/env python

# Starter script for filling dvmdostem input files. Some real data, some junk

# T. Carman, Feb 2024

import netCDF4 as nc
import glob

site_lat = 	61.3079
site_lon = -121.2992

# soil texture information in %
sand = 91
silt = 5
clay = 4

veg_class = 1  # CMT number

drain_class = 0  # Drainage class

# fire return interval 
fri = 2000
fri_severity = 1 
fri_jday_of_burn = 165
fri_area_of_burn = 10

# Topo info
elevation = 0  # meters
slope = 0      # degrees
aspect = 0     # degrees

#
# Now write data into the files....
#
with nc.Dataset('run-mask.nc', 'r+') as ds:
  ds.variables['run'][:] = 1

with nc.Dataset('soil-texture.nc', 'r+') as ds:
  ds.variables['pct_sand'][:] = sand
  ds.variables['pct_silt'][:] = silt
  ds.variables['pct_clay'][:] = clay

with nc.Dataset('vegetation.nc', 'r+') as ds:
  ds.variables['veg_class'][:] = veg_class

with nc.Dataset('drainage.nc', 'r+') as ds:
  ds.variables['drainage_class'][:] = drain_class

with nc.Dataset('fri-fire.nc', 'r+') as ds:
  ds.variables['fri'][:] = fri
  ds.variables['fri_severity'][:] = fri_severity
  ds.variables['fri_jday_of_burn'][:] = fri_jday_of_burn
  ds.variables['fri_area_of_burn'][:] = fri_area_of_burn

with nc.Dataset('topo.nc', 'r+') as ds:
  ds.variables['slope'][:] = slope
  ds.variables['elevation'][:] = elevation
  ds.variables['aspect'][:] = aspect

# Write lat & lon for all files
files = glob.glob("*")
for f in files:
  with nc.Dataset(f, 'r+') as ds:
    if 'lat' in ds.variables.keys() and 'lon' in ds.variables.keys():
      ds.variables['lat'][:] = site_lat
      ds.variables['lon'][:] = site_lon


# REMAINING TO FILL WITH REAL DATA:
#  - historic-climate.nc
#  - projected-climate.nc
#  - co2.nc
#  - projected-co2.nc
#  - historic-explicit-fire.nc
#  - projected-explicit-fire.nc

# Below here fills with crap data so that we can test run the model.

import numpy as np

YEARS = 50
MONTHS = YEARS*12

junk_float = np.random.random(MONTHS)
junk_int = np.random.randint(0,10,size=MONTHS)

with nc.Dataset('historic-climate.nc', 'r+') as ds:
  ds.variables['tair'][:] = junk_float * 100
  ds.variables['vapor_press'][:] = junk_float * 100
  ds.variables['precip'][:] = junk_float * 100
  ds.variables['nirr'][:] = junk_float * 100

with nc.Dataset('projected-climate.nc', 'r+') as ds:
  ds.variables['tair'][:] = junk_float * 100
  ds.variables['vapor_press'][:] = junk_float * 100
  ds.variables['precip'][:] = junk_float * 100
  ds.variables['nirr'][:] = junk_float * 100

with nc.Dataset('co2.nc', 'r+') as ds:
  ds.variables['co2'][:] = np.random.random(YEARS)*10

with nc.Dataset('projected-co2.nc', 'r+') as ds:
  ds.variables['co2'][:] = np.random.random(YEARS)*10

with nc.Dataset('historic-explicit-fire.nc', 'r+') as ds:
  ds.variables['exp_burn_mask'][:] = junk_int
  ds.variables['exp_jday_of_burn'][:] = junk_int
  ds.variables['exp_fire_severity'][:] = junk_int
  ds.variables['exp_area_of_burn'][:] = junk_int

with nc.Dataset('projected-explicit-fire.nc', 'r+') as ds:
  ds.variables['exp_burn_mask'][:] = junk_int
  ds.variables['exp_jday_of_burn'][:] = junk_int
  ds.variables['exp_fire_severity'][:] = junk_int
  ds.variables['exp_area_of_burn'][:] = junk_int



