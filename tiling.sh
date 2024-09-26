
########   USER SPECIFICATION   ########


### Script directory
scriptdir='/Users/helenegenet/Helene/TEM/INPUT/production/script_final'
### Output directory
outdir='/Volumes/5TI/DATAprocessed/DOWSCALING'
### CRU-JRA input directory
cjdir='/Volumes/DATAII/DATA/CLIMATE/CRUJRA'
### WORLDCLIM input directory
wcdir='/Volumes/DATAI/DATA/CLIMATE_DATA/worldclim'
### CMIP input directory
cmipdir='/Volumes/5TI/DATA/CLIMATE/CMIP6/scenarioCMIP'
### Path to the mask
mask='/Volumes/DATAII/DATA_processed/MASK/processed_data/aoi_5k_buff_6931.tiff'
### Longitudinal and latitudinal sizes of the tiles in number of pixels, npx and npy respectively.
npx=100
npy=100





########   PROCESSING   ########


### Assess metadata of the mask raster

## Coordinates of the upper left corners
origin=($(gdalinfo  $mask |sed -n -e '/^Origin = /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+)?'))
echo ${origin[@]}
## Size of the raster
size=($(gdalinfo  $mask |sed -n -e '/^Size is /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+)?'))
echo ${size[@]}
## Pixel resolution
res=($(gdalinfo  $mask |sed -n -e '/^Pixel Size = /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+)?'))
echo ${res[@]}
## Computation of the extent of the raster
left=$(echo ${origin[0]} | bc)
bottom=$(echo ${origin[1]}+${res[1]}*${size[1]} | bc)
top=$(echo ${origin[1]} | bc)
right=$(echo ${origin[0]}+${res[0]}*${size[0]} | bc)
extent=($left $bottom $right $top)
echo ${extent[@]}


### Tiling

## Compute the number tiles
# Number of horizontal tiles ntilex
modx=$(echo $((${size[0]} % $npx)) | bc)
if (( $(echo "$modx > 0.0" |bc -l) )); then
ntilex=$(echo $((${size[0]} / $npx))+1 | bc)
else
ntilex=$(echo $((${size[0]} / $npx)) | bc)
fi
# Number of vertical tiles ntiley
mody=$(echo $((${size[1]} % $npy)) | bc)
if (( $(echo "$mody > 0.0" |bc -l) )); then
ntiley=$(echo $((${size[1]} / $npy))+1 | bc)
else
ntiley=$(echo $((${size[1]} / $npy)) | bc)
fi

## Loop through tiles
for h in $(seq 1 $(printf '%.0f\n' ${ntilex}));do
echo $h 
for v in $(seq 1 $(printf '%.0f\n' ${ntiley}));do
echo $v 
# 1- Compute the extent of the tile
# Horizontal indices
h0=$(($h-1))
xmin=$(echo $left+$npx*$h0*${res[0]} | bc)
if [[ $h == $(printf '%.0f\n' ${ntilex}) ]]; then
xmax=$(echo $xmin+$modx*${res[0]} | bc)
else	
xmax=$(echo $xmin+$npx*${res[0]} | bc)
fi
# Vertical indices
v0=$(($v-1))
ymin=$(echo $bottom+$npy*$v0*${res[0]} | bc)
if [[ $v == $(printf '%.0f\n' ${ntiley}) ]]; then
ymax=$(echo $ymin+$mody*${res[0]} | bc)
else	
ymax=$(echo $ymin+$npy*${res[0]} | bc)
fi
# Tile extent
tileext=($xmin $ymin $xmax $ymax)
echo ${tileext[@]}
# 2- check that the mask has active pixels in the tile
# Crop the subregion from the mask raster
gdalwarp -overwrite -of netCDF -r bilinear -s_srs EPSG:6931 -t_srs EPSG:6931 -tr ${res[0]} ${res[1]} -te ${tileext[@]} $mask $outdir'/tmp.nc'
ncrename -O -h -v Band1,active $outdir'/tmp.nc'
ncwa -O -h -v active -a x,y -y total $outdir'/tmp.nc' $outdir'/tmp2.nc'
check=$(ncdump $outdir'/tmp2.nc' | sed -n -e '/^ active = /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+[ee][+-][0-9]+)?')
if [ "${check%.*}" -ge "1" ]; then
# Create a tile directory
dirname='H'$(printf "%0"$(echo "${#ntilex}")"d" $h)'_V'$(printf "%0"$(echo "${#ntiley}")"d" $v)
mkdir $outdir'/'$dirname
# Crop the mask to entire rows or coumns of NAs from the mask
newextent=($(python3 $scriptdir'/tiling_croping.py' $outdir'/tmp.nc' ${res[0]} | tr -d '[],'))
echo ${newextent[@]}
gdalwarp -overwrite -of GTiff -r bilinear -s_srs EPSG:6931 -t_srs EPSG:6931 -tr ${res[0]} ${res[1]} -te ${newextent[@]} $mask $outdir'/'$dirname'/mask.tiff'
gdalwarp -overwrite -of GTiff -r bilinear -s_srs EPSG:6931 -t_srs EPSG:6931 -tr ${res[0]} ${res[1]} -te ${newextent[@]} $mask $outdir'/mask_H'$(printf "%0"$(echo "${#ntilex}")"d" $h)'_V'$(printf "%0"$(echo "${#ntiley}")"d" $v)'.tiff'
fi
rm 	$outdir'/tmp.nc' $outdir'/tmp2.nc'
done
done





