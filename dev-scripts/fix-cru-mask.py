"""code to fix cru precip and dswrf data masks"""

from temds.datasources import crujra, annual
from pathlib import Path
import numpy as np
import xarray as xr
import gc


## UPDATE THIS IF RUNNING LOCALLY
data_root = Path('...')

callback = lambda fn: int(Path(fn).name.split('.')[-4])

files = data_root.joinpath('02-arctic/cru-jra/')
import joblib

out_root = data_root.joinpath('02-arctic/cru-jra-fixed')

files = sorted(list(files.glob('*.nc')))
# print(files)
last = 0
for idx in range(0,len(files),5):
    if idx == 0:
        continue
    
    # print(last, idx)
    local = files[last:idx]
    # print(files[last:idx])
    last = idx
    data = []
    for file in local:
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
