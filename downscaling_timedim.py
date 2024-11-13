import os
import xarray as xr
import sys
import argparse

parser = argparse.ArgumentParser(description='Argument description')
parser.add_argument('in_path', type=str,help='path to the monthly output file to be edited')
parser.add_argument('out_path', type=str,help='path to the monthly output file to be edited')
args = parser.parse_args()

dd = xr.open_dataset(args.in_path)
dd = dd.sortby("time")
dd.to_netcdf(args.out_path,unlimited_dims='time',format='NETCDF4', mode='w')

#dd = xr.open_dataset('/Volumes/5TII/DATAprocessed/DOWNSCALING/H01_V05/CRU_JRA/cj_correction_monthly.nc')