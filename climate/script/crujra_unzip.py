import os
import pandas as pd
import xarray as xr
import gzip
import numpy as np


crujradir = '/Volumes/LaCie/CRUJRA/data/'
crujraunzipdir = '/Volumes/BACKUP2018/DATA/CRU_JRA/data_unzip/'
#crujravarlist = ['pre','dlwrf','dswrf','tmp','spfh','pres']
crujravarlist = ['dlwrf','tmp','spfh','pres']
crujravarlist = ['dlwrf']
out = pd.DataFrame()
for var in crujravarlist:
	print(var)
	for y in range(1901,2022):
		print(y)
		if os.path.exists(os.path.join(crujradir,var,'crujra.v2.4.5d.' + var + '.' + str(y) + '.365d.noc.nc')):
			print('file exists!')
		else:
			with gzip.open(os.path.join(crujradir,var,'crujra.v2.4.5d.' + var + '.' + str(y) + '.365d.noc.nc.gz')) as fp:
				ds = xr.open_dataset(fp)
				ds.to_netcdf(os.path.join(crujradir,var,'crujra.v2.4.5d.' + var + '.' + str(y) + '.365d.noc.nc'))