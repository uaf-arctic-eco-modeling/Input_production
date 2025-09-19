#!/usr/bin/env python

"""
demo creating topography dataset from cloud
"""
from temds.logger import Logger, DEBUG
from temds.datasources.dataset import TEMDataset

import sys
from pathlib import Path
import matplotlib.pyplot as plt

import argparse
import textwrap

def existing_path(string):
    path = Path(string)
    if not path.exists():
        parser.error(f"Path does not exist: {path}")
    return path


parser = argparse.ArgumentParser(
formatter_class=argparse.RawDescriptionHelpFormatter,
description=textwrap.dedent('''
    Demo for working with topo data.
''')
)
parser.add_argument('data_path', nargs=1, type=existing_path, metavar=('DATA PATH'),
    help=textwrap.dedent('''Path to the source data'''))

parser.add_argument('extent_raster', nargs=1, type=existing_path, metavar=('EXTENT RASTER'),
    help=textwrap.dedent('''Path to a raster whose extents are used to subset/query the worldclim data.'''))

parser.add_argument('--download', action='store_true', 
    help=textwrap.dedent('''Flag for whether to download data if not found locally'''))


args = parser.parse_args()

log = Logger([], DEBUG)
log.info(f'Data is at {args.data_path}')
log.info(f'Extent is from {args.extent_raster}')

if args.download:
    log.info('Downloading data')

topo = TEMDataset.from_topo(
    args.data_path[0],
    download=args.download,
    extent_raster=args.extent_raster[0],
    logger=log
)

topo.save("/tmp/topo.nc", overwrite=True)

log.info('TEMDataset.verify returns tuple (True, []) when data is TEMDS ready')
log.info(f'Results of TEMDataset.verify: {topo.verify()}')

fig, axes= plt.subplots (1,1, dpi=100)
im = axes.imshow(topo.dataset['elevation'].data, origin='lower')
fig.colorbar(im, ax=axes)
axes.set_title('Topography Elevation')
plt.savefig("/tmp/topo.png")
plt.show()

### Here is how to save the data
# topo.save('topography.nc', overwrite=True)