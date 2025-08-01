"""
gdal tools
----------

gdal helpers
"""
import numpy as np
from osgeo import gdal

gdal.UseExceptions()

from functools import cache

@cache
def clip_gdal_opt(dest, source, resample_alg, run_primer, nd_as_array):
    no_data = np.nan
    if nd_as_array:
        no_data = [np.nan for i in range(source.RasterCount)]

    if run_primer:
        gdal.Warp(dest, source, warpOptions =['NUM_THREADS=4'],)#multithread=True)
    gdal.Warp(
        dest, source,
        srcNodata=no_data,
        dstNodata=no_data,
        resampleAlg=resample_alg,
        warpOptions =['NUM_THREADS=4'],
        # multithread=True
    )
    dest.FlushCache()
    return dest

#cant cache dict
def clip_opt_2 (dest, source, vars_dict, resample_alg, run_primer, nd_as_array):
    data_arrays = {}
    no_data = np.nan
    if nd_as_array:
        no_data = [np.nan for i in range(source.RasterCount)]

    for var in vars_dict:
        cur = vars_dict[var]
        source.WriteArray(cur)
        source.FlushCache() ## ensures data is in gdal dataset

        # run twice first to 'prime' the objects, other wise coastal data is
        # missing in result
        # dest = clip_gdal_opt(dest, source, resample_alg, run_primer, no_data)
        if run_primer:
            gdal.Warp(dest, source, multithread=True)
        gdal.Warp(
            dest, source,
            srcNodata=no_data,
            dstNodata=no_data,
            resampleAlg=resample_alg,
            multithread=True
        )
        dest.FlushCache()
        
        data_arrays[var] = dest.ReadAsArray()
    return data_arrays