#!/usr/bin/env python
import matplotlib.pyplot as plt
import xarray as xr
import numpy as np


def calc_diff(arr1, arr2):
  #diff = arr1 - np.flip(arr2, axis=1)
  diff = arr1-arr2
  return diff


def comp_1(ds_A, ds_B, A_tag, B_tag, var, tstep=0):
  '''
  Make a 3 panel figure with images of the data at a given time step.
  Left is dataset A, middle is dataset B, right is the difference (A-B).
  Colorbars are scaled to the extents of the data in both datasets, over
  the entire time series. The difference colorbar is scaled to the max
  absolute difference.
  '''
  VAR = var
  TSTEP = tstep

  diff = calc_diff(ds_A[VAR].data, ds_B[VAR].data)

  diff_min = np.abs(np.nanmin(diff.flatten()))
  diff_max = np.abs(np.nanmax(diff.flatten()))

  limit = max(diff_min, diff_max)
  print(f"max abs diff = {limit}")

  fig, axes = plt.subplots(1,3, figsize=(12,6))

  ds_A_max = np.nanmax(ds_A[VAR][TSTEP].data)
  ds_A_min = np.nanmin(ds_A[VAR][TSTEP].data)
  ds_B_max = np.nanmax(ds_B[VAR][TSTEP].data)
  ds_B_min = np.nanmin(ds_B[VAR][TSTEP].data)

  print(f"A {A_tag} {VAR} min={ds_A_min}, max={ds_A_max}")
  print(f"B {B_tag} {VAR} min={ds_B_min}, max={ds_B_max}")

  cbar_min = min(ds_A_min, ds_B_min)
  cbar_max = max(ds_A_max, ds_B_max)
  print(f"cbar min={cbar_min}, max={cbar_max}")

  A_img  = axes[0].imshow(ds_A[VAR][TSTEP].data, origin='lower', vmin=cbar_min, vmax=cbar_max)
  B_img = axes[1].imshow(ds_B[VAR][TSTEP].data, origin='lower', vmin=cbar_min, vmax=cbar_max)
  diff = axes[2].imshow(diff[TSTEP], origin='lower', cmap='coolwarm', vmin=-limit, vmax=limit)
  
  axes[0].set_title(f'ds_A ({A_tag})')
  axes[1].set_title(f'ds_B ({B_tag})')
  axes[2].set_title('Difference (A-B)')

  plt.colorbar(A_img, ax=axes[0])
  plt.colorbar(B_img, ax=axes[1])
  plt.colorbar(diff, ax=axes[2])

  plt.suptitle(f'Comparison of {VAR} at time step {TSTEP}')
  plt.tight_layout()

  plt.show()

def comp_2(ds_A, ds_B, A_tag, B_tag, var):
  '''
  Make a 2 panel figure:
   - boxplot of the differences over all time steps
   - and a time series plot of the differences in the mins and maxes over all 
     the timesteps.
  '''

  fig, axes = plt.subplots(2,1, figsize=(12,6))

  diff = calc_diff(ds_A[var].data, ds_B[var].data)

  diffbox = axes[0].boxplot(diff.flatten(), whis=[5, 95], showfliers=True)

  ts_diff_min = np.nanmin(diff, axis=(1,2))
  ts_diff_max = np.nanmax(diff, axis=(1,2))

  diffts_min = axes[1].plot(ts_diff_min, label='min')
  diffts_max = axes[1].plot(ts_diff_max, label='max')


  plt.show()




if __name__ == "__main__":

  ds_A = xr.open_dataset("working/05-tiles-TEM/H00_V08/historic-climate.nc")
  ds_B = xr.open_dataset("hg-samples/H01_V09/input/historic-climate.nc")

  a_tag = "This codebase"
  b_tag = "Helene's codebase"

  T=0

  #from IPython import embed; embed()

  comp_1(ds_A, ds_B, a_tag, b_tag, 'tair', tstep=T)
  comp_1(ds_A, ds_B, a_tag, b_tag, 'precip', tstep=T)
  comp_1(ds_A, ds_B, a_tag, b_tag, 'vapor_press', tstep=T)
  comp_1(ds_A, ds_B, a_tag, b_tag, 'nirr', tstep=T)

  comp_2(ds_A, ds_B, a_tag, b_tag, 'tair')
  comp_2(ds_A, ds_B, a_tag, b_tag, 'precip')
  comp_2(ds_A, ds_B, a_tag, b_tag, 'vapor_press')
  comp_2(ds_A, ds_B, a_tag, b_tag, 'nirr')