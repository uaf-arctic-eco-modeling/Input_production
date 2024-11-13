
### Author: Hélène Genet, hgenet@alaska.edu 
### Institution: Arctic Eco Modeling
### Team, Institute of Arctic Biology, University of Alaska Fairbanks 
### Date: September 23 2024 
### Description: 
### Command: $ 



########   USER SPECIFICATION   ########

### Path to directory to store the data downloaded
scriptdir='/Users/helenegenet/Helene/TEM/INPUT/production/script_final/'

### Path to directory to store the data downloaded
indir='/Volumes/5TII/DATA/CLIMATE/'

### WORLD CLIM related information
## List of variables to download
wcvarlist=('tmin' 'tmax' 'tavg' 'prec' 'srad' 'wind' 'vapr')

### CRU-JRA related information
## Version of the dataset
cjversion='2.5'
## Account information for CEDA FTP
usrname='hgenet'
psswrd='i6,(~Anze^9k'
## List of variables to download
cjvarlist=('tmin' 'tmax' 'tmp' 'pre' 'dswrf' 'ugrd' 'vgrd' 'spfh' 'pres')
## time period to download
cjstartyr=1901
cjendyr=2023
## Resolution in degree
cjres=0.5
### AOI shapefile in EPSG:4326 (WGS84)
mask4326='/Volumes/5TI/DATAprocessed/MASK/processed_data/aoi_4326.shp'
### AOI shapefile in EPSG:6931
mask6931='/Volumes/5TI/DATAprocessed/MASK/processed_data/aoi_5k_buff_6931.shp'
### Cumulated length of month of year for non-leap years
nlyc=(31 59 90 120 151 181 212 243 273 304 334 365)
#Frequency of daily data
tfreq=4


### CMIP related information
## Version of the dataset
cmipversion='6'
## List of variables to download
cmipvarlist='daily_maximum_near_surface_air_temperature,daily_minimum_near_surface_air_temperature,near_surface_air_temperature,near_surface_specific_humidity,near_surface_wind_speed,precipitation,sea_level_pressure'
#sclist='ssp1_2_6,ssp2_4_5,ssp3_7_0,ssp5_8_5'
sclist='ssp3_7_0,ssp5_8_5'
#modlist='access_cm2,mri_esm2_0,cmcc_cm2_sr5'
modlist='access_cm2,mri_esm2_0'
#modlist='cmcc_esm2'




########   PROCESSING   ########


### Boundaries in EPSG 4326
# Get shapefile layer name
filename=$(basename -- "$mask4326")
mask4326l=${filename%.*}
# Reproject the mask shapefile projected in WGS1984
ext=($(ogrinfo -so $mask4326 $mask4326l |sed -n -e '/^Extent: /p' | grep -Eo '[+-]?[0-9]+([.][0-9]+)?'))
echo ${ext[@]}
# Include the 5 km buffer (~0.1 degree) + the resolution of the CRU_JRA dataset
ext4326=()
ext4326[0]=$(echo ${ext[0]} - 0.1 - $cjres  | bc)
ext4326[1]=$(echo ${ext[1]} - 0.1 - $cjres  | bc)
ext4326[2]=$(echo ${ext[2]} + 0.1 + $cjres  | bc)
ext4326[3]=$(echo ${ext[3]} + 0.1 + $cjres  | bc)
# Keep the bounds reasonable
if (( $(echo "${ext4326[0]} < -180.0" |bc -l) )); then
  ext4326[0]=-180.0
fi
if (( $(echo "${ext4326[1]} < -90.0" |bc -l) )); then
  ext4326[1]=-90.0
fi
if (( $(echo "${ext4326[2]} > 180.0" |bc -l) )); then
  ext4326[2]=180.0
fi
if (( $(echo "${ext4326[3]} > 90.0" |bc -l) )); then
  ext4326[3]=90.0
fi
echo ${ext4326[@]}


### WorldClim 

## Create storage directory
if [ -d $indir'WorldClim' ]; then
  echo 'directory exists ... remove'
  rm -r $indir'WorldClim'
fi
mkdir $indir'WorldClim'
cd $indir'WorldClim'

## Download the data
# variable loop
for var in "${wcvarlist[@]}"; do
  echo $var
  wget 'https://geodata.ucdavis.edu/climate/worldclim/2_1/base/wc2.1_30s_'$var'.zip'
done

## Uncompress the data
cd $indir'WorldClim'
for f in  *.zip; do
  echo $f
  unzip $f
done



### CRU-JRA 

## Create storage directory
if [ -d $indir'CRU_JRA' ]; then
  echo 'directory exists ... remove'
  rm -r $indir'CRU_JRA'
fi
mkdir $indir'CRU_JRA'
cd $indir'CRU_JRA'

## Download the data
cd $indir'CRU_JRA'
for y in $(seq $cjstartyr $cjendyr); do
  echo $y
  for var in "${cjvarlist[@]}"; do
    wget -r 'ftp://'$usrname':'$psswrd'@ftp.ceda.ac.uk/badc/cru/data/cru_jra/cru_jra_'$cjversion'/data/'$var'/crujra.v'$cjversion'.5d.'$var'.'$y'.365d.noc.nc.gz'
  done
done

## Move the data to the input directory
mv $indir'CRU_JRA/ftp.ceda.ac.uk/badc/cru/data/cru_jra/cru_jra_'$cjversion'/data/'*  $indir'CRU_JRA/'
rm -r $indir'CRU_JRA/ftp.ceda.ac.uk'

## Create a secondary storage directory
if [ -d $indir'CRU_JRA_daily' ]; then
  echo 'directory exists ... remove'
  rm -r $indir'CRU_JRA_daily'
fi
mkdir $indir'CRU_JRA_daily'
cd $indir'CRU_JRA_daily'

## Crop and summarize the data from 6-hourly to daily
cd $indir'CRU_JRA_daily'
for y in $(seq $cjstartyr $cjendyr); do
  echo $y
  # Loop through variables
  for var in "${cjvarlist[@]}"; do
    echo $var
    gunzip -c $indir'CRU_JRA/'$var'/crujra.v2.5.5d.'$var'.'$y'.365d.noc.nc.gz' > $indir'CRU_JRA_daily/cj_'$var'_'$y'.nc'
    # Crop the original data to area of interest
    ncks -O -h -d lat,${ext4326[1]},${ext4326[3]} $indir'CRU_JRA_daily/cj_'$var'_'$y'.nc' $indir'CRU_JRA_daily/cj_'$var'_'$y'.nc'
    # Fix missing and fill values from the attributes so they are the same across all variables
    ncatted -O -h -a eulaVlliF_,,d,c, $indir'CRU_JRA_daily/cj_'$var'_'$y'.nc' $indir'CRU_JRA_daily/cj_'$var'_'$y'.nc'
    ncatted -O -h -a _FillValue,,o,f,1.e+20 $indir'CRU_JRA_daily/cj_'$var'_'$y'.nc' $indir'CRU_JRA_daily/cj_'$var'_'$y'.nc'
    ncatted -O -h -a missing_value,,o,f,1.e+20 $indir'CRU_JRA_daily/cj_'$var'_'$y'.nc' $indir'CRU_JRA_daily/cj_'$var'_'$y'.nc'
    # Summarize 6-hourly data to daily data
    if [[ $var == 'pre' ]] || [[ $var == 'dswrf' ]] ; then
      ncra --mro -O -d time,0,,4,4 -y total $indir'CRU_JRA_daily/cj_'$var'_'$y'.nc' $indir'CRU_JRA_daily/cj_'$var'_'$y'.nc'
    else
      ncra --mro -O -d time,0,,4,4 -y avg $indir'CRU_JRA_daily/cj_'$var'_'$y'.nc' $indir'CRU_JRA_daily/cj_'$var'_'$y'.nc'
    fi
    # Append all variables into a single yearly file
    if [[ $var == "${varlist[1]}" ]] ;then
      cp $indir'CRU_JRA_daily/cj_'$var'_'$y'.nc' $indir'CRU_JRA_daily/crujra_'$y'.nc'
    else
      ncatted -O -h -a eulaVlliF_,,d,c, $indir'CRU_JRA_daily/cj_'$var'_'$y'.nc' $indir'CRU_JRA_daily/cj_'$var'_'$y'.nc'
      ncks -A -h $indir'CRU_JRA_daily/cj_'$var'_'$y'.nc' $indir'CRU_JRA_daily/crujra_'$y'.nc'
      ncatted -O -h -a eulaVlliF_,,d,c, $indir'CRU_JRA_daily/crujra_'$y'.nc' $indir'CRU_JRA_daily/crujra_'$y'.nc'
    fi
  done
  rm $indir'CRU_JRA_daily/cj_'*
done





### CMIP 

## Create storage directory
if [ -d $indir'CMIP' ]; then
  echo 'directory exists ... remove'
  rm -r $indir'CMIP'
fi
mkdir $indir'CMIP'
cd $indir'CMIP'

## Install the necessary libraries
pip install cdsapi -U
pip install requests -U

## Download the data using the python script
export cmipdir=$indir'CMIP'
export cmipversion=$cmipversion
export gcm_list=${modlist[0]}
export sc_list=${sclist[0]}
export var_list=${cmipvarlist[0]}
python3 $scriptdir'data_download_CMIP.py'

## Uncompress the data
cd indir'CMIP'
for f in  *.zip; do
  echo $f
  unzip $f
  rm *.json *.png
done
