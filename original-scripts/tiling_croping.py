import os
import xarray as xr
import sys
import argparse

parser = argparse.ArgumentParser(description='Argument description')
parser.add_argument('mask_path', type=str,help='path to the mask of the sub-region to be examined')
parser.add_argument('resolution', type=float,help='resolution of the sub-region mask to be examined')
args = parser.parse_args()

res = float(args.resolution)

dd = xr.open_dataset(args.mask_path)
dd = dd.to_dataframe()
dd.reset_index(inplace=True)
#extent = [dd.x.min()-(res/2), dd.y.min()-(res/2), dd.x.max()+(res/2), dd.y.max()+(res/2)]
dd = dd[dd['active']==1]
extent = [dd.x.min()-(res/2), dd.y.min()-(res/2), dd.x.max()+(res/2), dd.y.max()+(res/2)]
print(extent)