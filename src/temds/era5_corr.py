from temds.constants import  get_month_slice
import operator
import xarray as xr

op_table = {
    'tair_avg': operator.sub,
    'prec':operator.truediv, 
    'vapo':operator.truediv, 
    'nirr':operator.truediv
}

def calc_era5_corrections(era5_baseline, reference, era5_daily):
    corr=[]
    for var, op in op_table.items():
        # print(var, op)
        cf = xr.where(
            reference.dataset[var] == 0, 
            1, 
            op( era5_baseline.dataset[var], reference.dataset[var])
        )
        temp = era5_daily.dataset[var] 
        
        
        downscaled_array = []
        for mn_ix in range(12): # 0 based
            mn_slice = get_month_slice(mn_ix)
        
            monthly = xr.where(cf[mn_ix] == 0, 0, op(temp[mn_slice], cf[mn_ix]))
        
                    
            downscaled_array.append( monthly ) 
    
        corr.append(xr.concat(downscaled_array, dim='time').transpose('time', 'y','x'))
        # xr.concat(downscaled_array)
    corr = xr.merge(corr)#[['time', 'x', 'y']]
    return corr
