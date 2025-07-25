#!/usr/bin/env python
"""code to fix cru precip and dswrf data masks

This exists because in our initial run on the cloud of the "crop to arctic,
resample to daily from hourly", the cru precip and dswrf data was summed with an
algorithm that did not properly handle no data values, resulting in some grid
cells being zero when they should have been nodata.

We fixed the code that does the crop/resample, but that step was slow and never
got bundled up into an easy thing to run, so here we just fix the data that has
already been processed. It is fixed by applying the tmax mask to the other
variables.
"""

from temds.datasources import crujra, annual
from pathlib import Path
import numpy as np
import xarray as xr
import gc
import joblib




## UPDATE THIS IF RUNNING LOCALLY
data_root = Path('working')

callback = lambda fn: int(Path(fn).name.split('.')[-4])

files = data_root.joinpath('02-arctic/cru-jra-25/')

out_root = data_root.joinpath('02-arctic/cru-jra-fixed')

files = sorted(list(files.glob('*.nc')))

last = 0
block_size = 5
for idx in range(0,len(files),block_size):
    data = []
    block = files[idx:idx + block_size]
    print(block)

    for file in block:
        print(file)
        if out_root.joinpath(file.name).exists():
            continue

        temp = crujra.AnnualDaily(None, file,  year_override_callback=callback)
        idx = np.isnan(temp.dataset['tmax'].values[0])
        for var in list(temp.dataset.data_vars):
            if np.isnan(temp.dataset[var].values[0][0][0]):
                continue
            # print(var)
            temp.dataset[var].values[:,idx] = np.nan
        # fn = file.name
        temp.dataset.attrs['data_year'] = temp.year
        data.append(temp)
    # # temp.save(f'/media/rwspicer/data/V3/tem/02-arctic/cru-jra-fixed/{fn}', overwrite=True)
    # # break
    if data == []:
        continue
    cru_ats = crujra.AnnualTimeSeries(data)

    with joblib.parallel_config(backend="loky", n_jobs=10, verbose=20):
        cru_ats.save(out_root,'crujra.arctic.v2.5.5d.{year}.365d.noc.nc', parallel=True)
    
    del(data)
    del(cru_ats)
    gc.collect()
