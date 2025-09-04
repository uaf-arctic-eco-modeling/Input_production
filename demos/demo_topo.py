#!/usr/bin/env python

"""
demo creating topography dataset from cloud
"""
from temds.logger import Logger, DEBUG
from temds.datasources.dataset import TEMDataset

import sys
from pathlib import Path
import matplotlib.pyplot as plt

try:
    data_path = Path(sys.argv[1])
    extent_raster = Path(sys.argv[2])

    try:
        download = sys.argv[3].lower() == 'download'
    except:
        download = False
except:
    print("""
    Run this demo with: 
          
    if data is local
        python demo_topo.py <data_path> <extent_raster> 

    or to download data first:
        python demo_topo.py <data_path> <extent_raster> download
""")

log = Logger([], DEBUG)
log.info(f'Data is at {data_path}')
log.info(f'Extent is from {extent_raster}')
if download:
    log.info('Downloading data')

topo = TEMDataset.from_topo(
    data_path,
    download=False,
    extent_raster=extent_raster,
    logger=log
)


log.info('TEMDataset.verify returns tuple (True, []) when data is TEMDS ready')
log.info(f'Results of TEMDataset.verify: {topo.verify()}')

fig, axes= plt.subplots (1,1, dpi=100)
im = axes.imshow(topo.dataset['elevation'].data[0], origin='lower')
fig.colorbar(im, ax=axes)
axes.set_title('Topography Elevation')

### Here is how to save the data
# topo.save('topography.nc', overwrite=True)