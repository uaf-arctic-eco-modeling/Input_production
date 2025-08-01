"""
demo creating worldclim dataset from cloud
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
        python demo_worldclim.py <data_path> <extent_raster> 
    
    or to download data first:
        python demo_worldclim.py <data_path> <extent_raster> download
""")

log = Logger([], DEBUG)
log.info(f'Data is at {data_path}')
log.info(f'Extent is from {extent_raster}')
if download:
    log.info('Downloading data')


wc_arctic = TEMDataset.from_worldclim(
            data_path, 
            download=download, 
            version='2.1', 
            resolution='30s', 
            in_vars='all', 
            extent_raster=extent_raster,
            overwrite=True, 
            logger=log,
            resample_alg='bilinear'
        )

log.info(f'dataset.verify returns tuple (True, []) when data is TEMDS ready')
log.info(f'Results of dataset.verify: {wc_arctic.verify()}')

fig, axes= plt.subplots (1,1, dpi=100)
im = axes.imshow(wc_arctic.dataset['tair_max'].data[0], origin='lower')
fig.colorbar(im, ax=axes)
axes.set_title('Worldclim Arctic Max Air Temp')

### Here is how to save the data
# wc_arctic.save('worldclim-arctic.nc', overwrite=True)