## Author: Helene Genet hgenet@alaska.edu
## Description: this script merge outputs across multiple tiles, 
# even when tiles are not adjacent. This script also summarize 
# the outputs when specified by user.


import os
import xarray as xr
import pandas as pd
from osgeo import gdal
import numpy as np
import glob


# List of emission scenarios
#sclist = ['ssp1_2_6','ssp2_4_5','ssp3_7_0','ssp5_8_5']
# List of global climate model
#gcmlist = ['access_cm2','mri_esm2_0']
# List of output tiles to merge
#tilelist = ['H10_V14','H10_V18']


#### USER INFORMATION ####

### Paths
## Path to the inputs
indir = '/Volumes/5TIV/PROCESSED/TILES2_0_out'
## Path to the outputs
outdir = '/Volumes/5TIV/PROCESSED/TEM_OUT'
## Path to the merging/synthesis directory
synthdir = '/Volumes/5TIV/PROCESSED/TEM_OUT_synth'
## Path to mask
maskpath = '/Volumes/5TIV/PROCESSED/MASK/aoi_5k_buff_6931_2_0.tiff'
## Path to dvm-dos-tem directory
temdir = '/Users/helenegenet/Helene/TEM/DVMDOSTEM/dvm-dos-tem'


### Synthesis level
# Do you want to synthesize the monthly outputs yearly?
yearsynth = True
# Do you want to synthesize the outputs across commpartment?
compsynth = True
# Do you want to synthesize the outputs by PFT?
pftsynth = True
# Do you want to synthesize the outputs by layer?
layersynth = True






#### LISTINGS ####

### Listing available tiles, scenarios and output variables
tilelist = []
simlist = []
outflist = []
for tile in os.listdir(outdir):
  if (os.path.isdir(os.path.join(outdir, tile))) & (not tile.startswith('.')):
    tilelist.append(tile)
    for simulation in os.listdir(os.path.join(outdir, tile)):
      if (os.path.isdir(os.path.join(outdir, tile, simulation))) & (not simulation.startswith('.')):
        simlist.append(simulation)
        for outf in os.listdir(os.path.join(outdir, tile, simulation)):
          if (os.path.isfile(os.path.join(outdir, tile, simulation, outf))) & (not outf.startswith('.')):
            outflist.append(outf)

simlist = list(set(simlist))
outflist = list(set(outflist))
varlist = list(set([item.split('_')[0] for item in outflist]))




#### CREATE CANVAS ####

### Get the extent of all the tiles 
xminlist = []
xmaxlist = []
yminlist = []
ymaxlist = []
for d in tilelist:
  mask = xr.open_dataset(os.path.join(indir,d,'run-mask.nc'))
  xminlist.append(mask.X.min().values.item())
  xmaxlist.append(mask.X.max().values.item())
  yminlist.append(mask.Y.min().values.item())
  ymaxlist.append(mask.Y.max().values.item())

### Crop the mask to the total extent of all the tiles
## Convert the mask tiff to netcdf
gdal.Translate(os.path.join(synthdir,'mask_all.nc'), maskpath, format='NetCDF')
## Crop mask to extent
crop_mask = xr.open_dataset(os.path.join(synthdir,'mask_all.nc')).sel(y=slice(min(yminlist), max(ymaxlist)), x=slice(min(xminlist), max(xmaxlist)))
crop_mask.to_netcdf(os.path.join(synthdir,'canvas.nc'))





#### MERGING OUTPUTS ####

### Reading the outvarlist file to a dataframe
ovl = pd.read_csv(os.path.join(temdir, 'config', 'output_spec.csv'))

### Scenario and Variable loop
var = varlist[11]
sim = simlist[0]
## Variable loop
for var in varlist:
  print('Variable:', var)
  ## Simulationvar loop
  for sim in simlist:
    print('  Simulation:', sim)
    for t in range(len(tilelist)):
      tile = tilelist[t]
      #print(t)
      # Read in the tile data and mask
      if os.path.exists(glob.glob(outdir + '/' + tile + '/' + sim + '/' + var + '*.nc')[0]):
        out = xr.open_dataset(glob.glob(outdir + '/' + tile + '/' + sim + '/' + var + '*.nc')[0])
        msk = xr.open_dataset(os.path.join(indir, tile, 'run-mask.nc'))
        # Read in temporal resolution
        tempres = os.path.basename(glob.glob(outdir + '/' + tile + '/' + sim + '/' + var + '*.nc')[0]).split('_')[1]
        if (tempres == 'monthly') & (yearsynth == True):
          tempres = 'yearly'
          if ovl[ovl['Name'] == var]['Yearsynth'].values[0] != 'invalid':
            op = ovl[ovl['Name'] == var]['Yearsynth'].values[0]
            codstg = "out = out[var].resample(time='Y')." + op + "(skipna=False).to_dataset()"
            exec(codstg)
        if ('pftpart' in list(out[var].dims)) & (compsynth == True):
          if ovl[ovl['Name'] == var]['Yearsynth'].values[0] != 'invalid':
            op = ovl[ovl['Name'] == var]['Yearsynth'].values[0]
            codstg = "out = out." + op + "(dim = 'pftpart', skipna=False)"
            exec(codstg)
        if ('pft' in list(out[var].dims)) & (pftsynth == True):
          if ovl[ovl['Name'] == var]['Pftsynth'].values[0] != 'invalid':
            op = ovl[ovl['Name'] == var]['Pftsynth'].values[0]
            codstg = "out = out." + op + "(dim = 'pft', skipna=False)"
            exec(codstg)
        if ('layer' in list(out[var].dims)) & (layersynth == True):
          if ovl[ovl['Name'] == var]['Yearsynth'].values[0] != 'invalid':
            op = ovl[ovl['Name'] == var]['Yearsynth'].values[0]
            codstg = "out = out." + op + "(dim = 'layer', skipna=False)"
            exec(codstg)
        # Add coordinate values to x and y of the tile output dataset
        out = out.assign_coords(x=("x", msk["X"].values),y=("y", msk["Y"].values))
        # Create the canevas dataset for combining
        if t == 0:
          # Get fill value from output file
          varfv = out[var].encoding.get('_FillValue')
          # Identify (additional) dimensions associated with this variable
          #adddimlist = [item for item in list(out[var].dims) if item not in {'x','y'}]
          dimname = list(out[var].dims)
          # Create the empty dataset of the croped mask that will be the canvas for combining tiles
          dimlengthlist = []
          for dim in list(out[var].dims):
            #print(dim)
            if dim == 'x':
              l = crop_mask.x.shape[0]
            elif dim == 'y':
              l = crop_mask.y.shape[0]
            else:
              l = out[dim].shape[0]
            dimlengthlist.append(l)
          # Create the coordinates dataset
          coords = {}
          for i in range(len(dimname)):
            if dimname[i] == 'x':
              coords[dimname[i]] = crop_mask.x.values
            elif dimname[i] == 'y':
              coords[dimname[i]] = crop_mask.y.values
            else:
              coords[dimname[i]] = out[dimname[i]].values
          # Create the variable dataset
          data_vars = {var: (tuple(dimname), np.full(tuple(dimlengthlist), varfv))}
          # Create the canevas
          canevas = xr.Dataset(data_vars, coords=coords)
          canevas.attrs = out.attrs
          varattrs = out[var].attrs
          varattrs['_FillValue'] = varfv
          canevas[var].attrs=out[var].attrs
          canevas.encoding = out.encoding
        # Combining the tile dataset to the canevas
        canevas = out.combine_first(canevas)
    canevas['y'] = crop_mask['y']
    canevas['x'] = crop_mask['x']
    canevas['x'].attrs = crop_mask['x'].attrs
    #canevas.x.encoding = crop_mask.x.encoding
    canevas['y'].attrs = crop_mask['y'].attrs
    #canevas.y.encoding = crop_mask.y.encoding
    canevas.to_netcdf(os.path.join(synthdir,var + '_' + sim + '_' + tempres + '.nc'))


