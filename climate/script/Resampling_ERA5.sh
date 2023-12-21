#! /bin/bash
setopt interactivecomments

##### Resampling CRU-JRA data #####

## Path to the grid/mask directory
maskdir='/Volumes/LaCie/DATA_processed/MASK/'
## Path to original data
indir='/Users/helenegenet/Helene/TEM/INPUT/ERA5/'
## Path to outputs 
outdir='/Volumes/LaCie/DATA_processed/CLIMATE/ERA5_60N_EPSG6931/'
## List of climate variables
varnclist=('2m_dewpoint_temperature' '2m_temperature' 'surface_solar_radiation_downwards' 'total_precipitation')
varlist=('d2m' 't2m' 'ssrd' 'tp')

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
## Number of sections on the horizontal (nx) and vertical (ny) sides to split the main mask into sub-regions
nx=10
ny=10
## Yearly loop
for y in {1980..1981}; do
	echo $y
	## Monthly loop
	for m in {1..12}; do
		echo $m
		## Loop through variables
		# Append all variables into a single yearly file
		for vn in {1..$(("${#varlist[@]}"))}; do
			if [[ $vn == 1 ]]; then
				cp $indir'download_daily_mean_'$varnclist[$vn]'_'$y'_'$(printf "%02d" $m)'.nc' $outdir'ERA5_'$y'_'$(printf "%02d" $m)'.nc'
				# Fix missing and fill values from the attributes so they are the same across all variables
				ncatted -O -h -a eulaVlliF_,,d,c, $outdir'ERA5_'$y'_'$(printf "%02d" $m)'.nc'
				ncatted -O -h -a _FillValue,,o,f,1.e+20 $outdir'ERA5_'$y'_'$(printf "%02d" $m)'.nc'
				ncatted -O -h -a missing_value,,o,f,1.e+20 $outdir'ERA5_'$y'_'$(printf "%02d" $m)'.nc'
			else
				ncks -A -h $indir'download_daily_mean_'$varnclist[$vn]'_'$y'_'$(printf "%02d" $m)'.nc' $outdir'ERA5_'$y'_'$(printf "%02d" $m)'.nc'
				# Fix missing and fill values from the attributes so they are the same across all variables
				ncatted -O -h -a eulaVlliF_,,d,c, $outdir'ERA5_'$y'_'$(printf "%02d" $m)'.nc'
				ncatted -O -h -a _FillValue,,o,f,1.e+20 $outdir'ERA5_'$y'_'$(printf "%02d" $m)'.nc'
				ncatted -O -h -a missing_value,,o,f,1.e+20 $outdir'ERA5_'$y'_'$(printf "%02d" $m)'.nc'
			fi
		done
		## Compute the extent of the single subregion for downscaling
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
		gdalwarp -overwrite -of netCDF -r bilinear -s_srs EPSG:6931 -t_srs EPSG:6931 -tr $res -te $extent $maskdir'mask.tif' $outdir$dirname'/tmp.nc'
		# Check that the sub-region's mask has any pixel that will be processed
		ncap2 -O -h -s 'where(Band1<0) Band1=0; maskttl=Band1.total($y,$x)' $outdir$dirname'/tmp.nc' $outdir$dirname'/tmp.nc' 
		check=$(ncks -O -h -v 'maskttl'  $outdir$dirname'/tmp.nc' | sed -n -e '/^    maskttl = /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+[ee][+-][0-9]+)?')
		if [ "${check%.*}" -ge "1" ]; then
		# Daily loop
		timel=($(ncdump -h $outdir'ERA5_'$y'_'$(printf "%02d" $m)'.nc'|sed -n -e '/	time = /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+)?'))
		for d in {1..$timel}; do
			echo $d
			# Compute day of year
			doy=$(($( date -j -f "%Y%m%d" $y$(printf "%02d" $m)$(printf "%02d" $d) +%j )))
			# Extract the original input for the selected day d
			ncks -O -h -d time,$(($d-1)) $outdir'ERA5_'$y'_'$(printf "%02d" $m)'.nc' $outdir$dirname'/tmp.nc'
			# Loop through variables
			for var in "${varlist[@]}"; do
				# Transform, clip and resample the climate variable daily data to the sub-region's mask CRS, extent, and resolution respectivly
				gdalwarp -overwrite -of netCDF -r bilinear -s_srs EPSG:4326 -t_srs EPSG:6931 -tr 1000 -1000 -te $extent NETCDF:$outdir$dirname'/tmp.nc':$var $outdir$dirname'/tmp_'$var'.nc'
				# Rename coordinate dimensions 
				ncrename -O -h -d x,lon -d y,lat -v x,lon -v y,lat $outdir$dirname'/tmp_'$var'.nc' $outdir$dirname'/tmp_'$var'.nc'
				# Rename Band 1 to the variable's name and set value for the time dimension (reset to 1 by default during transformation) to the DOY value
				ncap2 -O -h -s 'defdim("time",1); time[$time]='$doy'; '$var'[$time,$lat,$lon]=Band1' $outdir$dirname'/tmp_'$var'.nc' $outdir$dirname'/tmp_'$var'.nc'
				# Make the time dimension a record dimension for appending
				ncks -O -h --mk_rec_dmn time -x -v Band1 $outdir$dirname'/tmp_'$var'.nc' $outdir$dirname'/tmp_'$var'.nc'
				# Appending the variable files together
				if [[ $var == "${varlist[1]}" ]] ;then
					cp $outdir$dirname'/tmp_'$var'.nc' $outdir$dirname'/ERA5_'$y'_'$(printf "%03d" $d)'.nc'
				else
					ncks -A -h $outdir$dirname'/tmp_'$var'.nc' $outdir$dirname'/ERA5_'$y'_'$(printf "%03d" $d)'.nc'
				fi
			done
		done
		# Appending all the daily outputs along the time dimension
		ncrcat -O -h $outdir$dirname'/ERA5_'$y'_'???'.nc' $outdir$dirname'/ERA5_'$y'_'$(printf "%02d" $m)'_r.nc'
		rm $outdir$dirname'/ERA5_'$y'_'???'.nc' $outdir$dirname'/tmp'*
	fi
done



			# Loop through variables
			for vn in {1..$(("${#varlist[@]}"))}; do
				if [[ $vn == '1' ]]; then  
					cp 
				else
					print $varlist[$vn]
				fi
			done
				# Transform, clip and resample the climate variable daily data to the sub-region's mask CRS, extent, and resolution respectivly
				gdalwarp -overwrite -of netCDF -r bilinear -s_srs EPSG:4326 -t_srs EPSG:6931 -tr 1000 -1000 -te $extent NETCDF:$outdir$dirname'/tmp.nc':$var $outdir$dirname'/tmp_'$var'.nc'
				# Rename coordinate dimensions 
				ncrename -O -h -d x,lon -d y,lat -v x,lon -v y,lat $outdir$dirname'/tmp_'$var'.nc' $outdir$dirname'/tmp_'$var'.nc'
				# Rename Band 1 to the variable's name and set value for the time dimension (reset to 1 by default during transformation) to the DOY value
				ncap2 -O -h -s 'defdim("time",1); time[$time]='$d'; '$var'[$time,$lat,$lon]=Band1' $outdir$dirname'/tmp_'$var'.nc' $outdir$dirname'/tmp_'$var'.nc'
				# Make the time dimension a record dimension for appending
				ncks -O -h --mk_rec_dmn time -x -v Band1 $outdir$dirname'/tmp_'$var'.nc' $outdir$dirname'/tmp_'$var'.nc'
				# Appending the variable files together
				if [[ $var == "${varlist[1]}" ]] ;then
					cp $outdir$dirname'/tmp_'$var'.nc' $outdir$dirname'/crujra.v2.4.5d.'$y'_'$(printf "%03d" $d)'.nc'
				else
					ncks -A -h $outdir$dirname'/tmp_'$var'.nc' $outdir$dirname'/crujra.v2.4.5d.'$y'_'$(printf "%03d" $d)'.nc'
				fi
			done
		done
		# Appending all the daily outputs along the time dimension
		ncrcat -O -h $outdir$dirname'/crujra.v2.4.5d.'$y'_'???'.nc' $outdir$dirname'/crujra.v2.4.5d.'$y'r.nc'
		rm $outdir$dirname'/crujra.v2.4.5d.'$y'.nc' $outdir$dirname'/crujra.v2.4.5d.'$y'_'???'.nc' $outdir$dirname'/tmp'*
	fi
done


### Process for a multiple sub-regions
## Number of sections on the horizontal (nx) and vertical (ny) sides to split the main mask into sub-regions
nx=10
ny=10
## Yearly loop
for y in {1901..2022}; do
	echo $y
	## Loop through variables
	for var in "${varlist[@]}"; do
		echo $var
		# Crop the original data to north of 55oN
		ncks -O -h -d lat,55.,90. $indir$var'/crujra.v2.4.5d.'$var'.'$y'.365d.noc.nc' $outdir'tmp_'$var'.nc'
		# Fix missing and fill values from the attributes so they are the same across all variables
		ncatted -O -h -a eulaVlliF_,,d,c, $outdir'tmp_'$var'.nc' $outdir'tmp_'$var'.nc'
		ncatted -O -h -a _FillValue,,o,f,1.e+20 $outdir'tmp_'$var'.nc' $outdir'tmp_'$var'.nc'
		ncatted -O -h -a missing_value,,o,f,1.e+20 $outdir'tmp_'$var'.nc' $outdir'tmp_'$var'.nc'
		# Summarize 6-hourly data to daily data
		if [[ $var == 'pre' ]] || [[ $var == 'dlwrf' ]] ; then
			ncra --mro -O -d time,0,,4,4 -y total $outdir'tmp_'$var'.nc' $outdir'tmp_'$var'.nc'
		else
			ncra --mro -O -d time,0,,4,4 -y avg $outdir'tmp_'$var'.nc' $outdir'tmp_'$var'.nc'
		fi
		# Append all variables into a single yearly file
		if [[ $var == "${varlist[1]}" ]] ;then
			cp $outdir'tmp_'$var'.nc' $outdir'crujra.v2.4.5d.'$y'.nc'
		else
			ncatted -O -h -a eulaVlliF_,,d,c, $outdir'tmp_'$var'.nc' $outdir'tmp_'$var'.nc'
			ncks -A -h $outdir'tmp_'$var'.nc' $outdir'crujra.v2.4.5d.'$y'.nc'
			ncatted -O -h -a eulaVlliF_,,d,c, $outdir'crujra.v2.4.5d.'$y'.nc' $outdir'crujra.v2.4.5d.'$y'.nc'
		fi
	done
	rm $outdir'tmp_'*
	## Compute the extent of the single subregion for downscaling
	# Loop through horizontal indices
	for i in {1..$nx}; do
		print $i
		xmin=$(($origin[1]+$res[1]*($i-1)*$size[1]/$nx))
		xmax=$(($origin[1]+$res[1]*$i*$size[1]/$nx))
		# Loop through vertical indices
		for j in {1..$ny}; do
			print $j
			ymin=$(($origin[2]+$res[2]*$j*$size[2]/$ny))
			ymax=$(($origin[2]+$res[2]*($j-1)*$size[2]/$ny))
			# Compute the extent of the subregion
			extent=($xmin $ymin $xmax $ymax)
			print $extent
			# Create a subdirectory to store the outputs for the subregion
			dirname='H'$(printf "%03d" $i)'_V'$(printf "%03d" $j)
			mkdir $outdir$dirname
			# Crop the subregion from the mask raster
			gdalwarp -overwrite -of netCDF -r bilinear -s_srs EPSG:6931 -t_srs EPSG:6931 -tr $res -te $extent $maskdir'mask.tif' $outdir$dirname'/tmp.nc'
			# Check that the sub-region's mask has any pixel that will be processed
			ncap2 -O -h -s 'where(Band1<0) Band1=0; maskttl=Band1.total($y,$x)' $outdir$dirname'/tmp.nc' $outdir$dirname'/tmp.nc' 
			check=$(ncks -O -h -v 'maskttl'  $outdir$dirname'/tmp.nc' | sed -n -e '/^    maskttl = /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+[ee][+-][0-9]+)?')
			if [ "${check%.*}" -ge "1" ]; then
				# Daily loop
				for d in {1..365}; do
					echo $d
					# Extract the original input for the selected day d
					ncks -O -h -d time,$(($d-1)) $outdir'crujra.v2.4.5d.'$y'.nc' $outdir$dirname'/tmp.nc'
					# Loop through variables
					for var in "${varlist[@]}"; do
						# Transform, clip and resample the climate variable daily data to the sub-region's mask CRS, extent, and resolution respectivly
						gdalwarp -overwrite -of netCDF -r bilinear -s_srs EPSG:4326 -t_srs EPSG:6931 -tr 1000 -1000 -te $extent NETCDF:$outdir$dirname'/tmp.nc':$var $outdir$dirname'/tmp_'$var'.nc'
						# Rename coordinate dimensions 
						ncrename -O -h -d x,lon -d y,lat -v x,lon -v y,lat $outdir$dirname'/tmp_'$var'.nc' $outdir$dirname'/tmp_'$var'.nc'
						# Rename Band 1 to the variable's name and set value for the time dimension (reset to 1 by default during transformation) to the DOY value
						ncap2 -O -h -s 'defdim("time",1); time[$time]='$d'; '$var'[$time,$lat,$lon]=Band1' $outdir$dirname'/tmp_'$var'.nc' $outdir$dirname'/tmp_'$var'.nc'
						# Make the time dimension a record dimension for appending
						ncks -O -h --mk_rec_dmn time -x -v Band1 $outdir$dirname'/tmp_'$var'.nc' $outdir$dirname'/tmp_'$var'.nc'
						# Appending the variable files together
						if [[ $var == "${varlist[1]}" ]] ;then
							cp $outdir$dirname'/tmp_'$var'.nc' $outdir$dirname'/crujra.v2.4.5d.'$y'_'$(printf "%03d" $d)'.nc'
						else
							ncks -A -h $outdir$dirname'/tmp_'$var'.nc' $outdir$dirname'/crujra.v2.4.5d.'$y'_'$(printf "%03d" $d)'.nc'
						fi
					done
				done
				# Appending all the daily outputs along the time dimension
				ncrcat -O -h $outdir$dirname'/crujra.v2.4.5d.'$y'_'???'.nc' $outdir$dirname'/crujra.v2.4.5d.'$y'r.nc'
				rm $outdir$dirname'/crujra.v2.4.5d.'$y'.nc' $outdir$dirname'/crujra.v2.4.5d.'$y'_'???'.nc' $outdir$dirname'/tmp'*
			fi
		done
	done
done

