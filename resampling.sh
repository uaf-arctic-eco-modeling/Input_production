

########   USER SPECIFICATION   ########


### Script directory
scriptdir='/Users/helenegenet/Helene/TEM/INPUT/production/script_final'
### Output directory
outdir='/Volumes/5TIII/DATAprocessed/DOWNSCALING'
outdir='/Volumes/5TIII/DATAprocessed/DOWNSCALING2'
outdir='/Volumes/5TIII/DATAprocessed/test'
if [ -d $outdir ]; then
  echo "Directory exists."
else
  mkdir -p $outdir
fi
### CRU-JRA input directory
cjdir='/Volumes/5TIII/DATA/CLIMATE/CRU_JRA_daily'
## Resolution in degree
cjres=0.5
## time period to download
#cjstartyr=1901
cjstartyr=1970
cjendyr=2023
## List of variables for the CRU_JRA dataset
cjvarlist=('tmin' 'tmax' 'tmp' 'pre' 'dswrf' 'ugrd' 'vgrd' 'spfh' 'pres')
### WORLDCLIM input directory
wcdir='/Volumes/5TIII/DATA/CLIMATE/WorldClim'
## List of variables for the WORLD_CLIM dataset
wcvarlist=('tmin' 'tmax' 'tavg' 'prec' 'srad' 'wind' 'vapr')
## length of each month of year
monthlengthlist=(31 28 31 30 31 30 31 31 30 31 30 31)
### CMIP input directory
cmipdir='/Volumes/5TIII/DATA/CLIMATE/CMIP'




########   PROCESSING   ########



for dir in $outdir/* ; do
  if [ -d $dir ]; then
    echo $dir

#dir='/Volumes/5TII/DATAprocessed/test/H01_V05'
#dir='/Volumes/5TII/DATAprocessed/test/H02_V14'
#dir='/Volumes/5TII/DATAprocessed/test/H12_V14'
#dir='/Volumes/5TII/DATAprocessed/test/H03_V09'

    ### Compute the spatial references of the tile masks.

    ## Compute the extent of the original tile mask in 6931 EPSG
    msk_tile_6931_o=($(gdalinfo  $dir'/mask_6931.tiff' |sed -n -e '/^Origin = /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+)?'))
    msk_tile_6931_sz=($(gdalinfo  $dir'/mask_6931.tiff' |sed -n -e '/^Size is /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+)?'))
    msk_tile_6931_res=($(gdalinfo  $dir'/mask_6931.tiff' |sed -n -e '/^Pixel Size = /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+)?'))
    left=$(echo ${msk_tile_6931_o[0]} | bc)
    bottom=$(echo ${msk_tile_6931_o[1]}+${msk_tile_6931_res[1]}*${msk_tile_6931_sz[1]} | bc)
    top=$(echo ${msk_tile_6931_o[1]} | bc)
    right=$(echo ${msk_tile_6931_o[0]}+${msk_tile_6931_res[0]}*${msk_tile_6931_sz[0]} | bc)
    ext_tile_6931=($left $bottom $right $top)
    echo 'Sub-region extent in NSIDC EASE-Grid 2.0 North (EPSG 6931): ' ${ext_tile_6931[@]}
    
    ### Compute the extent of the reprojected mask with a buffer zone to prevent any gap resulting from the reprojection and croping
    msk_tile_4326_o=($(gdalinfo  $dir'/mask_4326.tiff' |sed -n -e '/^Origin = /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+)?'))
    msk_tile_4326_sz=($(gdalinfo  $dir'/mask_4326.tiff' |sed -n -e '/^Size is /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+)?'))
    msk_tile_4326_res=($(gdalinfo  $dir'/mask_4326.tiff' |sed -n -e '/^Pixel Size = /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+)?'))
    left=$(echo ${msk_tile_4326_o[0]} | bc)
    bottom=$(echo ${msk_tile_4326_o[1]}+${msk_tile_4326_res[1]}*${msk_tile_4326_sz[1]} | bc)
    top=$(echo ${msk_tile_4326_o[1]} | bc)
    right=$(echo ${msk_tile_4326_o[0]}+${msk_tile_4326_res[0]}*${msk_tile_4326_sz[0]} | bc)
    ext_tile_4326=($left $bottom $right $top)
#    echo 'Sub-region extent in WGS84 (EPSG 4326): '${ext_tile_4326[@]}
    # Include the 5 km buffer (~0.1 degree) + the resolution of the CRU_JRA dataset
    ext_tile_4326_buffer=()
    ext_tile_4326_buffer[0]=$(echo ${ext_tile_4326[0]} - 0.1 - $cjres  | bc)
    ext_tile_4326_buffer[1]=$(echo ${ext_tile_4326[1]} - 0.1 - $cjres  | bc)
    ext_tile_4326_buffer[2]=$(echo ${ext_tile_4326[2]} + 0.1 + $cjres  | bc)
    ext_tile_4326_buffer[3]=$(echo ${ext_tile_4326[3]} + 0.1 + $cjres  | bc)
    # Keep the bounds reasonable
    if (( $(echo "${ext_tile_4326_buffer[0]} < -180.0" |bc -l) )); then
      ext_tile_4326_buffer[0]=-180.0
    fi
    if (( $(echo "${ext_tile_4326_buffer[1]} < -90.0" |bc -l) )); then
      ext_tile_4326_buffer[1]=-90.0
    fi
    if (( $(echo "${ext_tile_4326_buffer[2]} > 180.0" |bc -l) )); then
      ext_tile_4326_buffer[2]=180.0
    fi
    if (( $(echo "${ext_tile_4326_buffer[3]} > 90.0" |bc -l) )); then
      ext_tile_4326_buffer[3]=90.0
    fi
    echo 'Sub-region extent in WGS84 (EPSG 4326, including buffer): '${ext_tile_4326_buffer[@]}
  
  
  
  
  
    ### WORLDCLIM resampling
  
    mkdir $dir'/WORLD_CLIM'
    for m in {1..12}; do
      echo $m
      ## Compute day of year
      doy=$(echo $( date -j -f "%Y%m%d" 1970$(printf "%02d" $m)01 +%j ) | sed 's/^0*//')
      ## Loop through variables
      for var in "${wcvarlist[@]}"; do
        echo $var
        gdalwarp -overwrite -of netCDF -r bilinear -s_srs EPSG:4326 -t_srs EPSG:6931 -tr ${msk_tile_6931_res[0]} ${msk_tile_6931_res[1]} -te ${ext_tile_6931[@]} $wcdir'/wc2.1_30s_'$var'_'$(printf "%02d" $m)'.tif' $dir'/WORLD_CLIM/tmp_'$var'_'$(printf "%02d" $m)'.nc'
        # Fix missing and fill values from the attributes so they are the same across all variables
        ncatted -O -h -a eulaVlliF_,,d,c, $dir'/WORLD_CLIM/tmp_'$var'_'$(printf "%02d" $m)'.nc' $dir'/WORLD_CLIM/tmp_'$var'_'$(printf "%02d" $m)'.nc'
        ncatted -O -h -a _FillValue,,o,f,1.e+20 $dir'/WORLD_CLIM/tmp_'$var'_'$(printf "%02d" $m)'.nc' $dir'/WORLD_CLIM/tmp_'$var'_'$(printf "%02d" $m)'.nc'
        ncatted -O -h -a missing_value,,o,f,1.e+20 $dir'/WORLD_CLIM/tmp_'$var'_'$(printf "%02d" $m)'.nc' $dir'/WORLD_CLIM/tmp_'$var'_'$(printf "%02d" $m)'.nc'
        # Rename coordinate dimensions 
        ncrename -O -h -d x,lon -d y,lat -v x,lon -v y,lat $dir'/WORLD_CLIM/tmp_'$var'_'$(printf "%02d" $m)'.nc' $dir'/WORLD_CLIM/tmp_'$var'_'$(printf "%02d" $m)'.nc'
        # Rename Band 1 to the variable name and set value for the time dimension (reset to 1 by default during transformation) to the DOY value
        ncap2 -O -h -s 'defdim("time",1); time[$time]='$doy'; '$var'[$time,$lat,$lon]=Band1' $dir'/WORLD_CLIM/tmp_'$var'_'$(printf "%02d" $m)'.nc' $dir'/WORLD_CLIM/tmp_'$var'_'$(printf "%02d" $m)'.nc'
        # Make the time dimension a record dimension for appending
        ncks -O -h --mk_rec_dmn time -x -v Band1 $dir'/WORLD_CLIM/tmp_'$var'_'$(printf "%02d" $m)'.nc' $dir'/WORLD_CLIM/tmp_'$var'_'$(printf "%02d" $m)'.nc'
        # Appending the variable files together
        if [[ $var == "${varlist[1]}" ]] ;then
          cp $dir'/WORLD_CLIM/tmp_'$var'_'$(printf "%02d" $m)'.nc' $dir'/WORLD_CLIM/wc_'$(printf "%02d" $m)'.nc'
        else
          ncks -A -h $dir'/WORLD_CLIM/tmp_'$var'_'$(printf "%02d" $m)'.nc' $dir'/WORLD_CLIM/wc_'$(printf "%02d" $m)'.nc'
        fi
        ncatted -O -h -a eulaVlliF_,,d,c, $dir'/WORLD_CLIM/wc_'$(printf "%02d" $m)'.nc' $dir'/WORLD_CLIM/wc_'$(printf "%02d" $m)'.nc'
        ncatted -O -h -a _FillValue,,o,f,1.e+20 $dir'/WORLD_CLIM/wc_'$(printf "%02d" $m)'.nc' $dir'/WORLD_CLIM/wc_'$(printf "%02d" $m)'.nc'
        ncatted -O -h -a missing_value,,o,f,1.e+20 $dir'/WORLD_CLIM/wc_'$(printf "%02d" $m)'.nc' $dir'/WORLD_CLIM/wc_'$(printf "%02d" $m)'.nc'
      done
      ncap2 -O -h -s'lat=float(lat); lon=float(lon);' $dir'/WORLD_CLIM/wc_'$(printf "%02d" $m)'.nc' $dir'/WORLD_CLIM/wc_'$(printf "%02d" $m)'.nc'
      rm $dir'/WORLD_CLIM/tmp_'*
    done
    # Appending all the monthly outputs along the time dimension
    ncrcat -O -h $dir'/WORLD_CLIM/wc_'$(printf "%02d" $m)'.nc' $dir'/WORLD_CLIM/wc.nc'
  
  
  
  
  
    ### CRU_JRA resampling
  
    mkdir $dir'/CRU_JRA'
    echo 'Downscaling CRU-JRA'
    ### Yearly loop
    for y in $(seq $cjstartyr $cjendyr); do
      ## Croping the data to the tile extent 
      ncks -O -h -d lat,${ext_tile_4326_buffer[1]},${ext_tile_4326_buffer[3]} -d lon,${ext_tile_4326_buffer[0]},${ext_tile_4326_buffer[2]} $cjdir'/crujra_'$y'.nc' $dir'/CRU_JRA/cj_'$y'.nc'
      # Fix missing and fill values from the attributes so they are the same across all variables
      ncatted -O -h -a eulaVlliF_,,d,c, $dir'/CRU_JRA/cj_'$y'.nc' $dir'/CRU_JRA/cj_'$y'.nc'
      ncatted -O -h -a _FillValue,,o,f,1.e+20 $dir'/CRU_JRA/cj_'$y'.nc' $dir'/CRU_JRA/cj_'$y'.nc'
      ncatted -O -h -a missing_value,,o,f,1.e+20 $dir'/CRU_JRA/cj_'$y'.nc' $dir'/CRU_JRA/cj_'$y'.nc'
      for var in "${cjvarlist[@]}"; do
        echo 'Year: ' $y ' Variable: ' $var
        gdalwarp -overwrite -of netCDF -r bilinear -s_srs EPSG:4326 -t_srs EPSG:6931 -tr ${msk_tile_6931_res[0]} ${msk_tile_6931_res[1]} -te ${ext_tile_6931[@]} NETCDF:$dir'/CRU_JRA/cj_'$y'.nc':$var $dir'/CRU_JRA/tmp_'$y'_'$var'.nc'
        # Reformating the resampled file
        python3 $scriptdir'/resampling_crujra.py' $dir'/CRU_JRA/tmp_'$y'_'$var'.nc' $y $var
        if [[ $var == "${cjvarlist[0]}" ]] ;then
          cp $dir'/CRU_JRA/tmp_'$y'_'$var'.nc' $dir'/CRU_JRA/cj_'$y'_rsmpl.nc'
          # Fix missing and fill values from the attributes so they are the same across all variables
          ncatted -O -h -a eulaVlliF_,,d,c, $dir'/CRU_JRA/cj_'$y'_rsmpl.nc' $dir'/CRU_JRA/cj_'$y'_rsmpl.nc'
          ncatted -O -h -a _FillValue,,o,f,1.e+20 $dir'/CRU_JRA/cj_'$y'_rsmpl.nc' $dir'/CRU_JRA/cj_'$y'_rsmpl.nc'
          ncatted -O -h -a missing_value,,o,f,1.e+20 $dir'/CRU_JRA/cj_'$y'_rsmpl.nc' $dir'/CRU_JRA/cj_'$y'_rsmpl.nc'
        else
#         ncks -A -h $outdir$dirname'/resampled/tmp_'$var'.nc' $outdir$dirname'/resampled/crujra.v2.4.5d.'$y'_'$(printf "%03d" $d)'.nc'
          ncks -A -h $dir'/CRU_JRA/tmp_'$y'_'$var'.nc' $dir'/CRU_JRA/cj_'$y'_rsmpl.nc'
          # Fix missing and fill values from the attributes so they are the same across all variables
          ncatted -O -h -a eulaVlliF_,,d,c, $dir'/CRU_JRA/cj_'$y'_rsmpl.nc' $dir'/CRU_JRA/cj_'$y'_rsmpl.nc'
          ncatted -O -h -a _FillValue,,o,f,1.e+20 $dir'/CRU_JRA/cj_'$y'_rsmpl.nc' $dir'/CRU_JRA/cj_'$y'_rsmpl.nc'
          ncatted -O -h -a missing_value,,o,f,1.e+20 $dir'/CRU_JRA/cj_'$y'_rsmpl.nc' $dir'/CRU_JRA/cj_'$y'_rsmpl.nc'
        fi
      done
      #done
      # Appending all the daily outputs along the time dimension
#     ncrcat -O -h $outdir$dirname'/resampled/crujra.v2.4.5d.'$y'_'???'.nc' $outdir$dirname'/resampled/crujra.v2.4.5d.'$y'r.nc'
     rm $dir'/CRU_JRA/tmp_'*
    done
  
  fi
done

