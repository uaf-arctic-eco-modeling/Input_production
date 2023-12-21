#! /bin/bash
setopt interactivecomments

##### Reprojecting WORLDCLIM data #####

## Path to the grid/mask directory
maskdir='/Volumes/LaCie/DATA_processed/MASK/'
## Path to original data
indir='/Volumes/DATA/DATA/CLIMATE_DATA/worldclim/'
## Path to outputs 
outdir='/Volumes/LaCie/DATA_processed/CLIMATE/WC_60N_EPSG6931/'
## List of climate variables
varlist=('prec' 'srad' 'tavg' 'vapr' 'wind')


## Assess metadata of the mask raster
# Coordinates of the upper left corners
origin=($(gdalinfo  $maskdir'mask.tif'|sed -n -e '/^Origin = /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+)?'))
# Size of the raster
size=($(gdalinfo  $maskdir'mask.tif'|sed -n -e '/^Size is /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+)?'))
# Pixel resolution
res=($(gdalinfo  $maskdir'mask.tif'|sed -n -e '/^Pixel Size = /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+)?'))
# Computation of the extent of the raster
extent=($origin[1] $(($origin[2]+$res[2]*$size[2])) $(($origin[1]+$res[1]*$size[1])) $origin[2])
echo $extent




### Process for a single sub-region
### Number of sections on the horizontal (nx) and vertical (ny) sides to split the main mask into sub-regions
nx=10
ny=10
# Compute the extent of the single subregion for downscaling
# Horizontal index
i=4
xmin=$(($origin[1]+$res[1]*($i-1)*$size[1]/$nx))
xmax=$(($origin[1]+$res[1]*$i*$size[1]/$nx))
# Vertical index
j=2
ymin=$(($origin[2]+$res[2]*$j*$size[2]/$ny))
ymax=$(($origin[2]+$res[2]*($j-1)*$size[2]/$ny))
# Compute the extent of the subregion
extent=($xmin $ymin $xmax $ymax)
# Create a subdirectory to store the outputs for the subregion
dirname='H'$(printf "%03d" $i)'_V'$(printf "%03d" $j)
mkdir $outdir$dirname
# Crop the subregion from the mask raster
gdalwarp -overwrite -of netCDF -r bilinear -s_srs EPSG:6931 -t_srs EPSG:6931 -tr 1000 -1000 -te $extent $maskdir'mask.tif' $outdir$dirname'/tmp.nc'
# Check that the sub-region's mask has any pixel that will be processed
ncap2 -O -h -s 'where(Band1<0) Band1=0; maskttl=Band1.total($y,$x)' $outdir$dirname'/tmp.nc' $outdir$dirname'/tmp.nc' 
check=$(ncks -O -h -v 'maskttl'  $outdir$dirname'/tmp.nc' | sed -n -e '/^    maskttl = /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+[ee][+-][0-9]+)?')
if [ "${check%.*}" -ge "1" ]; then
## Monthly loop
for m in {1..12}; do
	echo $m
	## Compute day of year
	doy=$(($( date -j -f "%Y%m%d" 1970$(printf "%02d" $m)01 +%j )))
	## Loop through variables
	for var in "${varlist[@]}"; do
		echo $var
		gdalwarp -overwrite -of netCDF -r bilinear -s_srs EPSG:4326 -t_srs EPSG:6931 -tr 1000 -1000 -te $extent $indir'wc2.1_30s_'$var'_'$(printf "%02d" $m)'.tif' $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc'
		# Fix missing and fill values from the attributes so they are the same across all variables
		ncatted -O -h -a eulaVlliF_,,d,c, $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc' $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc'
		ncatted -O -h -a _FillValue,,o,f,1.e+20 $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc' $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc'
		ncatted -O -h -a missing_value,,o,f,1.e+20 $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc' $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc'
		# Rename coordinate dimensions 
		ncrename -O -h -d x,lon -d y,lat -v x,lon -v y,lat $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc' $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc'
		# Rename Band 1 to the variable's name and set value for the time dimension (reset to 1 by default during transformation) to the DOY value
		ncap2 -O -h -s 'defdim("time",1); time[$time]='$doy'; '$var'[$time,$lat,$lon]=Band1' $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc' $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc'
		# Make the time dimension a record dimension for appending
		ncks -O -h --mk_rec_dmn time -x -v Band1 $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc' $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc'
		# Appending the variable files together
		if [[ $var == "${varlist[1]}" ]] ;then
			cp $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc' $outdir$dirname'/wc2.1_30s_'$(printf "%02d" $m)'.nc'
		else
			ncks -A -h $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc' $outdir$dirname'/wc2.1_30s_'$(printf "%02d" $m)'.nc'
		fi
		ncatted -O -h -a eulaVlliF_,,d,c, $outdir$dirname'/wc2.1_30s_'$(printf "%02d" $m)'.nc' $outdir$dirname'/wc2.1_30s_'$(printf "%02d" $m)'.nc'
		ncatted -O -h -a _FillValue,,o,f,1.e+20 $outdir$dirname'/wc2.1_30s_'$(printf "%02d" $m)'.nc' $outdir$dirname'/wc2.1_30s_'$(printf "%02d" $m)'.nc'
		ncatted -O -h -a missing_value,,o,f,1.e+20 $outdir$dirname'/wc2.1_30s_'$(printf "%02d" $m)'.nc' $outdir$dirname'/wc2.1_30s_'$(printf "%02d" $m)'.nc'
	done
	rm $outdir$dirname'/tmp_'*
done
# Appending all the monthly outputs along the time dimension
ncrcat -O -h $outdir$dirname'/wc2.1_30s_'??'.nc' $outdir$dirname'/wc2.1_30s.nc'



### Process for a multiple sub-regions
### Number of sections on the horizontal (nx) and vertical (ny) sides to split the main mask into sub-regions
nx=10
ny=10
# Compute the extent of the single subregion for downscaling
# Loop through horizontal indices
for i in {1..$nx}; do
	xmin=$(($origin[1]+$res[1]*($i-1)*$size[1]/$nx))
	xmax=$(($origin[1]+$res[1]*$i*$size[1]/$nx))
	# Loop through vertical indices
	for j in {1..$ny}; do
		ymin=$(($origin[2]+$res[2]*$j*$size[2]/$ny))
		ymax=$(($origin[2]+$res[2]*($j-1)*$size[2]/$ny))
		# Compute the extent of the subregion
		extent=($xmin $ymin $xmax $ymax)
		# Create a subdirectory to store the outputs for the subregion
		dirname='H'$(printf "%03d" $i)'_V'$(printf "%03d" $j)
		mkdir $outdir$dirname
		# Crop the subregion from the mask raster
		gdalwarp -overwrite -of netCDF -r bilinear -s_srs EPSG:6931 -t_srs EPSG:6931 -tr $res -te $extent $maskdir'mask.tif' $outdir$dirname'/tmp.nc'
		# Check that the sub-region's mask has any pixel that will be processed
		ncap2 -O -h -s 'where(Band1<0) Band1=0; maskttl=Band1.total($y,$x)' $outdir$dirname'/tmp.nc' $outdir$dirname'/tmp.nc' 
		check=$(ncks -O -h -v 'maskttl'  $outdir$dirname'/tmp.nc' | sed -n -e '/^    maskttl = /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+[ee][+-][0-9]+)?')
		if [ "${check%.*}" -ge "1" ]; then
		## Monthly loop
		for m in {1..12}; do
			echo $m
			## Compute day of year
			doy=$(($( date -j -f "%Y%m%d" 1970$(printf "%02d" $m)01 +%j )))
			## Loop through variables
			for var in "${varlist[@]}"; do
				echo $var
				gdalwarp -overwrite -of netCDF -r bilinear -s_srs EPSG:4326 -t_srs EPSG:6931 -tr $res -te $extent $indir'wc2.1_30s_'$var'_'$(printf "%02d" $m)'.tif' $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc'
				# Fix missing and fill values from the attributes so they are the same across all variables
				ncatted -O -h -a eulaVlliF_,,d,c, $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc' $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc'
				ncatted -O -h -a _FillValue,,o,f,1.e+20 $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc' $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc'
				ncatted -O -h -a missing_value,,o,f,1.e+20 $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc' $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc'
				# Rename coordinate dimensions 
				ncrename -O -h -d x,lon -d y,lat -v x,lon -v y,lat $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc' $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc'
				# Rename Band 1 to the variable's name and set value for the time dimension (reset to 1 by default during transformation) to the DOY value
				ncap2 -O -h -s 'defdim("time",1); time[$time]='$doy'; '$var'[$time,$lat,$lon]=Band1' $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc' $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc'
				# Make the time dimension a record dimension for appending
				ncks -O -h --mk_rec_dmn time -x -v Band1 $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc' $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc'
				# Appending the variable files together
				if [[ $var == "${varlist[1]}" ]] ;then
					cp $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc' $outdir$dirname'/wc2.1_30s_'$(printf "%02d" $m)'.nc'
				else
					ncks -A -h $outdir$dirname'/tmp_'$var'_'$(printf "%02d" $m)'.nc' $outdir$dirname'/wc2.1_30s_'$(printf "%02d" $m)'.nc'
				fi
				ncatted -O -h -a eulaVlliF_,,d,c, $outdir$dirname'/wc2.1_30s_'$(printf "%02d" $m)'.nc' $outdir$dirname'/wc2.1_30s_'$(printf "%02d" $m)'.nc'
				ncatted -O -h -a _FillValue,,o,f,1.e+20 $outdir$dirname'/wc2.1_30s_'$(printf "%02d" $m)'.nc' $outdir$dirname'/wc2.1_30s_'$(printf "%02d" $m)'.nc'
				ncatted -O -h -a missing_value,,o,f,1.e+20 $outdir$dirname'/wc2.1_30s_'$(printf "%02d" $m)'.nc' $outdir$dirname'/wc2.1_30s_'$(printf "%02d" $m)'.nc'
			done
			rm $outdir$dirname'/tmp_'*
		done
		# Appending all the monthly outputs along the time dimension
		ncrcat -O -h $outdir$dirname'/wc2.1_30s_'??'.nc' $outdir$dirname'/wc2.1_30s.nc'
	done
done

