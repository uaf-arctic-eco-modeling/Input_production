#!/bin/bash

# T. Carman, Feb 2024
#
# Generate empty template netcdf files for dvmdostem from a 
# folder of CDL files.
#
# Experimenting with keeping the specificaiton for dvmdostem
# in CDL format (as opposed to say generating files using a python 
# script).

CDL_FOLDER=$1

OUT_FOLDER="SAMPLEFILES"
mkdir -p $OUT_FOLDER
for FILE in $(ls $CDL_FOLDER); 
do

  #echo "${FILE%%.*}" # name
  #echo "${FILE%.*}"  # name.nc
  #echo "${FILE#*.}"  # nc.cdl
  #echo "${FILE##*.}" # cdl
  #echo ${FILE%%}     # name.nc.cdl
  #echo ""
  ncgen -o "$OUT_FOLDER/${FILE%.*}" "$CDL_FOLDER/$FILE"
done 
