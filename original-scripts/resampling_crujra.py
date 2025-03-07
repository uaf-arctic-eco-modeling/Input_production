import os
import xarray as xr
import pandas as pd
import shutil
import numpy as np
import sys
import argparse


parser = argparse.ArgumentParser(description='Argument description')
parser.add_argument('resample_path', type=str,help='path to the temporary resampled file for the sub-region of interest')
parser.add_argument('year', type=int,help='resolution of the sub-region mask to be examined')
parser.add_argument('var', type=str,help='resolution of the sub-region mask to be examined')
args = parser.parse_args()

print(args.resample_path, args.year, args.var)

year = int(args.year)
var = str(args.var)
ddo = xr.open_dataset(args.resample_path)
dd = ddo.to_dataframe()
dd.reset_index(inplace=True)
dd = pd.melt(dd, id_vars=['y','x'], value_vars=['Band' + str(s) for s in list(range(1,366))])
dd['time'] = pd.to_datetime(pd.Timestamp(str(year)+'-01-01')) - pd.to_datetime(pd.Timestamp('1901-01-01'))
dd['time'] = dd['time'].dt.days + dd['variable'].str[4:].astype(int)
dd = dd.rename(columns={'value': var, 'x': 'lon', 'y': 'lat'})
dd = dd.drop(columns=['variable'])
#dd = dd.sort_values(by=['time','y','x'])

nc = dd.set_index(['time', 'lat', 'lon']).to_xarray()
nc['lat'] = nc['lat'].astype(np.single)
nc['lon'] = nc['lon'].astype(np.single)
nc[var] = nc[var].astype(np.single)
nc['time'] = nc['time'].astype(np.intc)
nc['lat'].attrs={'standard_name':'latitude','long_name':'y coordinate of projection','units':'m'}
nc['lon'].attrs={'standard_name':'longitude','long_name':'x coordinate of projection','units':'m'}
nc[var].attrs={'_FillValue': -9999.0}
nc['time'].attrs={'units':'days since 1901-1-1 0:0:0','long_name':'time','calendar':'365_day','_FillValue': -9999.0}
nc.time.encoding['units'] = 'days since 1901-01-01 00:00:00'
nc.time.encoding['calendar'] = '365_day'
nc.time.encoding['long_name'] = 'time'
#nc['lambert_azimuthal_equal_area'] = ddo.lambert_azimuthal_equal_area
nc.attrs = ddo.attrs
nc.to_netcdf(args.resample_path,unlimited_dims='time',mode='w')

