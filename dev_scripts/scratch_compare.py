#!/usr/bin/env python
import matplotlib.pyplot as plt
import xarray as xr
import numpy as np
from matplotlib.widgets import Slider
from matplotlib.widgets import TextBox


def calc_diff(arr1, arr2):
  #diff = arr1 - np.flip(arr2, axis=1)
  diff = arr1-arr2
  return diff

def report_diff_stats(ds_A, ds_B, var):
  '''
  Report some stats on the differences between two datasets for a given variable.
  Datasets are expected to be the same shape and have dimensions (time, y, x).
  '''
  diff = calc_diff(ds_A[var].data, ds_B[var].data)

  diff_min = np.nanmin(diff)
  diff_max = np.nanmax(diff)
  diff_mean = np.nanmean(diff)
  diff_std = np.nanstd(diff)

  print(f"Stats for differences (A-B) for {var}:")
  print(f"  min: {diff_min:0.5f}")
  print(f"  max: {diff_max:0.5f}")
  print(f"  mean: {diff_mean:0.5f}")
  print(f"  std: {diff_std:0.5f}")
  print(f"Range of ds_A: {np.nanmin(ds_A[var].data):0.5f} to {np.nanmax(ds_A[var].data):0.5f}")
  print(f"Range of ds_B: {np.nanmin(ds_B[var].data):0.5f} to {np.nanmax(ds_B[var].data):0.5f}")


def comp_1(ds_A, ds_B, A_tag, B_tag, var, tstep=0):
  '''
  Make a 3 panel figure with images of the data at a given time step.
  Left is dataset A, middle is dataset B, right is the difference (A-B).
  Colorbars are scaled to the extents of the data in both datasets, over
  the entire time series. The difference colorbar is scaled to the max
  absolute difference.

  Datasets are expected to be the same shape and have dimensions (time, y, x).
  '''
  VAR = var
  TSTEP = tstep

  diff = calc_diff(ds_A[VAR].data, ds_B[VAR].data)

  diff_min = np.abs(np.nanmin(diff.flatten()))
  diff_max = np.abs(np.nanmax(diff.flatten()))

  limit = max(diff_min, diff_max)
  #print(f"max abs diff = {limit}")
  report_diff_stats(ds_A, ds_B, VAR)

  fig, axes = plt.subplots(1,3, figsize=(12,6))

  ds_A_max = np.nanmax(ds_A[VAR][TSTEP].data)
  ds_A_min = np.nanmin(ds_A[VAR][TSTEP].data)
  ds_B_max = np.nanmax(ds_B[VAR][TSTEP].data)
  ds_B_min = np.nanmin(ds_B[VAR][TSTEP].data)

  #print(f"A {A_tag} {VAR} min={ds_A_min}, max={ds_A_max}")
  #print(f"B {B_tag} {VAR} min={ds_B_min}, max={ds_B_max}")

  cbar_min = min(ds_A_min, ds_B_min)
  cbar_max = max(ds_A_max, ds_B_max)
  print(f"Setting cbar min={cbar_min}, max={cbar_max}")

  #from IPython import embed; embed()

  A_img  = axes[0].imshow(ds_A[VAR][TSTEP].data, origin='lower', vmin=cbar_min, vmax=cbar_max)
  B_img = axes[1].imshow(ds_B[VAR][TSTEP].data, origin='lower', vmin=cbar_min, vmax=cbar_max)
  diff = axes[2].imshow(diff[TSTEP], origin='lower', cmap='coolwarm', vmin=-limit, vmax=limit)
  
  axes[0].set_title(f'ds_A ({A_tag})')
  axes[1].set_title(f'ds_B ({B_tag})')
  axes[2].set_title('Difference (A-B)')

  plt.colorbar(A_img, ax=axes[0])
  plt.colorbar(B_img, ax=axes[1])
  plt.colorbar(diff, ax=axes[2])

  # Add a slider for time step selection
  ax_slider = plt.axes([0.2, 0.01, 0.6, 0.03])
  slider = Slider(
    ax=ax_slider,
    label='Time Step',
    valmin=0,
    valmax=ds_A[VAR].shape[0] - 1,
    valinit=TSTEP,
    valstep=1,
  )

  def update(val):
    t = int(slider.val)
    # Update images
    A_img.set_data(ds_A[VAR][t].data)
    B_img.set_data(ds_B[VAR][t].data)
    diff.set_data(calc_diff(ds_A[VAR].data, ds_B[VAR].data)[t])

    A_img.set_clim(np.nanmin(ds_A[VAR][t].data), np.nanmax(ds_A[VAR][t].data))
    B_img.set_clim(np.nanmin(ds_B[VAR][t].data), np.nanmax(ds_B[VAR][t].data))
    # diff_data = calc_diff(ds_A[VAR].data, ds_B[VAR].data)[t]
    # diff_limit = max(abs(np.nanmin(diff_data)), abs(np.nanmax(diff_data)))
    # diff.set_clim(-diff_limit, diff_limit)

    fig.suptitle(f'Comparison of {VAR} at time step {t}')
    fig.canvas.draw_idle()

  slider.on_changed(update)

  def slider_update(val):
    #textbox.set_val(str(int(val))) ## Keep slider and textbox in sync
    update(val)

  slider.on_changed(slider_update)

  plt.suptitle(f'Comparison of {VAR} at time step {TSTEP}')
  #plt.tight_layout()

  print("\n")
  return fig
  #plt.show()

def comp_3(ds_A, ds_B, A_tag, B_tag, var):

  fig, axes = plt.subplots(1,3, figsize=(12,6))
  diff = calc_diff(ds_A[var].data, ds_B[var].data)




def comp_2(ds_A, ds_B, A_tag, B_tag, var):
  '''
  Make a 2 panel figure:
   - boxplot of the differences over all time steps
   - and a time series plot of the differences in the mins and maxes over all 
     the timesteps.

  Datasets are expected to be the same shape and have dimensions (time, y, x).

  '''

  fig, axes = plt.subplots(2,1, figsize=(12,6), num='A-B ')

  diff = calc_diff(ds_A[var].data, ds_B[var].data)

  # Show the distribution of differences
  diffbox = axes[0].boxplot(diff.flatten(), whis=[2.5, 97.5], showfliers=True)

  ts_diff_min = np.nanmin(diff, axis=(1,2))
  ts_diff_max = np.nanmax(diff, axis=(1,2))
  ts_diff_mean = np.nanmean(diff, axis=(1,2))

  diffts_min = axes[1].plot(ts_diff_min, label='min')
  diffts_max = axes[1].plot(ts_diff_max, label='max')
  diffts_mean = axes[1].plot(ts_diff_mean, label='mean')

  axes[1].legend()

  axes[1].set_title(f'Time series of min, max, mean differences (A-B) for {var}')
  axes[0].set_title(f'Boxplot of differences (A-B) for {var}')
  axes[0].set_ylabel('A-B')
  axes[1].set_ylabel('A-B')
  axes[1].set_xlabel('Time step') 
  axes[1].axhline(0, color='red', linestyle='--', linewidth=0.5)


  return fig

  #plt.show()




if __name__ == "__main__":

  ds_A = xr.open_dataset("working/05-tiles-TEM/H00_V08/historic-climate.nc")
  #ds_B = xr.open_dataset("working/05-tiles-TEM/H00_V08/M2-historic-climate.nc")
  ds_B = xr.open_dataset("hg-samples/H01_V09/input/historic-climate.nc")

  a_tag = "This codebase"
  b_tag = "Helene's codebase"

  T=0

  #from IPython import embed; embed()

  for var in ['tair', 'precip', 'vapor_press', 'nirr']:
      comp_1(ds_A, ds_B, a_tag, b_tag, var, tstep=T)
      comp_2(ds_A, ds_B, a_tag, b_tag, var)
      plt.show()

  # comp_1(ds_A, ds_B, a_tag, b_tag, 'tair', tstep=T)
  # comp_1(ds_A, ds_B, a_tag, b_tag, 'precip', tstep=T)
  # comp_1(ds_A, ds_B, a_tag, b_tag, 'vapor_press', tstep=T)
  # comp_1(ds_A, ds_B, a_tag, b_tag, 'nirr', tstep=T)

  # comp_2(ds_A, ds_B, a_tag, b_tag, 'tair')
  # comp_2(ds_A, ds_B, a_tag, b_tag, 'precip')
  # comp_2(ds_A, ds_B, a_tag, b_tag, 'vapor_press')
  # comp_2(ds_A, ds_B, a_tag, b_tag, 'nirr')
