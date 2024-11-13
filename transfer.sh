#! /bin/bash


### Output directory
outdir='/Volumes/5TII/DATAprocessed/DOWNSCALING'

## Storing directory
stordir='/Volumes/5TII/DATAprocessed/storage'
if [ ! -d $stordir ]; then
  mkdir $stordir 
  mkdir $stordir'/daily' 
  mkdir $stordir'/monthly'
fi


## Historical time range
cjstartyr=1970
cjendyr=2023

## Scenario Time range
scstartyr=$(($cjendyr+1))
scendyr=2100




########   PROCESSING   ########




for dir in $outdir/* ; do
  if [ -d $dir ]; then
    basename $dir
    if [ -f $dir'/CRU_JRA/cj_correction_daily.nc' ]; then
      mv $dir'/CRU_JRA/cj_correction_daily.nc' $stordir'/daily/'$(basename $dir)'_CRUJRA25_historical_'$cjstartyr'_'$cjendyr'_daily.nc'
    fi
    if [ -f $dir'/CRU_JRA/cj_correction_monthly.nc' ]; then
      mv $dir'/CRU_JRA/cj_correction_monthly.nc' $stordir'/monthly/'$(basename $dir)'_CRUJRA25_historical_'$cjstartyr'_'$cjendyr'_monthly.nc'
    fi
  fi
done

