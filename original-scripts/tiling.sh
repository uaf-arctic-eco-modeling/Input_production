

########   USER SPECIFICATION   ########


### Script directory
scriptdir='/Users/helenegenet/Helene/TEM/INPUT/production/script_final'
### Output directory
outdir='/Volumes/5TII/DATAprocessed/DOWNSCALING'
if [ -d $outdir ]; then
  echo "Directory exists."
else
  mkdir -p $outdir
fi
### CRU-JRA input directory
cjdir='/Volumes/5TII/DATA/CLIMATE/CRU_JRA_daily'
## Resolution in degree
cjres=0.5
## time period to download
cjstartyr=1901
cjendyr=2023
## List of variables to download
cjvarlist=('tmin' 'tmax' 'tmp' 'pre' 'dswrf' 'ugrd' 'vgrd' 'spfh' 'pres')
### WORLDCLIM input directory
wcdir='/Volumes/5TII/DATA/CLIMATE/WorldClim'
### CMIP input directory
cmipdir='/Volumes/5TII/DATA/CLIMATE/CMIP'
### Path to the mask
mask='/Volumes/5TI/DATAprocessed/MASK/processed_data/aoi_5k_buff_6931.tiff'
### Longitudinal and latitudinal sizes of the tiles in number of pixels, npx and npy respectively.
npx=100
npy=100






########   PROCESSING   ########



## Assess metadata of the mask raster
# Coordinates of the upper left corners
msk_all_o=($(gdalinfo  $mask |sed -n -e '/^Origin = /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+)?'))
echo ${msk_all_o[@]}
# Size of the raster
msk_all_sz=($(gdalinfo  $mask |sed -n -e '/^Size is /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+)?'))
echo ${msk_all_sz[@]}
# Pixel resolution
msk_all_res=($(gdalinfo  $mask |sed -n -e '/^Pixel Size = /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+)?'))
echo ${msk_all_res[@]}
# Computation of the extent of the raster
msk_all_left=$(echo ${msk_all_o[0]} | bc)
msk_all_bottom=$(echo ${msk_all_o[1]}+${msk_all_res[1]}*${msk_all_sz[1]} | bc)
msk_all_top=$(echo ${msk_all_o[1]} | bc)
msk_all_right=$(echo ${msk_all_o[0]}+${msk_all_res[0]}*${msk_all_sz[0]} | bc)
ext_all_6931=($msk_all_left $msk_all_bottom $msk_all_right $msk_all_top)
echo ${ext_all_6931[@]}


### Tiling

## Compute the number tiles
# Number of horizontal tiles ntilex
modx=$(echo $((${msk_all_sz[0]} % $npx)) | bc)
if (( $(echo "$modx > 0.0" |bc -l) )); then
  ntilex=$(echo $((${msk_all_sz[0]} / $npx))+1 | bc)
else
  ntilex=$(echo $((${msk_all_sz[0]} / $npx)) | bc)
fi
# Number of vertical tiles ntiley
mody=$(echo $((${msk_all_sz[1]} % $npy)) | bc)
if (( $(echo "$mody > 0.0" |bc -l) )); then
  ntiley=$(echo $((${msk_all_sz[1]} / $npy))+1 | bc)
else
  ntiley=$(echo $((${msk_all_sz[1]} / $npy)) | bc)
fi
echo 'Total number of tiles - vertical:' $ntiley ', horizontal:' $ntilex


## Loop through tiles to select the ones that includes active cells and produce the mask for each of these tiles
for h in $(seq 1 $(printf '%.0f\n' ${ntilex}));do
  for v in $(seq 1 $(printf '%.0f\n' ${ntiley}));do
    echo "H: "$h" V: "$v 
    # 1- Compute the extent of the tile
    # Horizontal indices
    h0=$(($h-1))
    xmin=$(echo $msk_all_left+$npx*$h0*${msk_all_res[0]} | bc)
    if [[ $h == $(printf '%.0f\n' ${ntilex}) ]]; then
      xmax=$(echo $xmin+$modx*${msk_all_res[0]} | bc)
    else	
      xmax=$(echo $xmin+$npx*${msk_all_res[0]} | bc)
    fi
    # Vertical indices
    v0=$(($v-1))
    ymin=$(echo $msk_all_bottom+$npy*$v0*${msk_all_res[0]} | bc)
    if [[ $v == $(printf '%.0f\n' ${ntiley}) ]]; then
      ymax=$(echo $ymin+$mody*${msk_all_res[0]} | bc)
    else	
      ymax=$(echo $ymin+$npy*${msk_all_res[0]} | bc)
    fi
    # Tile extent
    ext_tile_ttl_6931=($xmin $ymin $xmax $ymax)
    echo ${ext_tile_ttl_6931[@]}
    # 2- check that the mask has active pixels in the tile
    # Crop the subregion from the mask raster
    gdalwarp -overwrite -of netCDF -r bilinear -s_srs EPSG:6931 -t_srs EPSG:6931 -tr ${msk_all_res[0]} ${msk_all_res[1]} -te ${ext_tile_ttl_6931[@]} $mask $outdir'/tmp.nc'
    ncrename -O -h -v Band1,active $outdir'/tmp.nc'
    ncwa -O -h -v active -a x,y -y total $outdir'/tmp.nc' $outdir'/tmp2.nc'
    check=$(ncdump $outdir'/tmp2.nc' | sed -n -e '/^ active = /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+[ee][+-][0-9]+)?')
    if [ "${check%.*}" -ge "1" ]; then
      # Create a tile directory
      dirname='H'$(printf "%0"$(echo "${#ntilex}")"d" $h)'_V'$(printf "%0"$(echo "${#ntiley}")"d" $v)
      mkdir $outdir'/'$dirname
      # Crop the mask to entire rows or columns of NAs from the mask
      ext_tile_6931=($(python3 $scriptdir'/tiling_croping.py' $outdir'/tmp.nc' ${msk_all_res[0]} | tr -d '[],'))
      echo ${ext_tile_6931[@]}
      gdalwarp -overwrite -of GTiff -r bilinear -s_srs EPSG:6931 -t_srs EPSG:6931 -tr ${msk_all_res[0]} ${msk_all_res[1]} -te ${ext_tile_6931[@]} $mask $outdir'/'$dirname'/mask_6931.tiff'
      # Convert the projection of the mask to the projection of the one for CRU-JRA
      gdalwarp -overwrite -of GTiff -r bilinear -s_srs EPSG:6931 -t_srs EPSG:4326 $outdir'/'$dirname'/mask_6931.tiff' $outdir'/'$dirname'/mask_4326.tiff'
    fi
    rm $outdir'/tmp.nc' $outdir'/tmp2.nc'
  done
done








