
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
indir='/Volumes/5TI/DATA/CLIMATE/INPUT/'

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

### CMIP related information
## Version of the dataset
cmipversion='6'
## List of variables to download
cmipvarlist='daily_maximum_near_surface_air_temperature,daily_minimum_near_surface_air_temperature,near_surface_air_temperature,near_surface_specific_humidity,near_surface_wind_speed,precipitation,sea_level_pressure'
sclist='ssp1_2_6,ssp2_4_5,ssp3_7_0,ssp5_8_5'
modlist='access_cm2,mri_esm2_0,cmcc_cm2_sr5'




########   PROCESSING   ########



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



### CRU-JRA 

## Create storage directory
if [ -d $indir'CRU_JRA' ]; then
	echo 'directory exists ... remove'
	rm -r $indir'CRU_JRA'
fi
mkdir $indir'CRU_JRA'
cd $indir'CRU_JRA'

## Download the data
for y in $(seq $cjstartyr $cjendyr); do
	echo $y
	for var in "${cjvarlist[@]}"; do
		wget -r 'ftp://'$usrname':'$psswrd'@ftp.ceda.ac.uk/badc/cru/data/cru_jra/cru_jra_'$cjversion'/data/'$var'/crujra.v'$cjversion'.5d.'$var'.'$y'.365d.noc.nc.gz'
	done
done

## Move the data to the input directory
mv $indir'CRU_JRA/ftp.ceda.ac.uk/badc/cru/data/cru_jra/cru_jra_'$cjversion'/data/'*  $indir'CRU_JRA/'
rm -r $indir'CRU_JRA/ftp.ceda.ac.uk'


### CMIP 

## Create storage directory
if [ -d $indir'CMIP' ]; then
	echo 'directory exists ... remove'
	rm -r $indir'CMIP'
fi
mkdir $indir'CMIP'
cd $indir'CMIP'

## Install the necessary libraries
pip install cdsapi
pip install requests

## Download the data using the python script
export cmipdir=$indir'CMIP'
export cmipversion=$cmipversion
export gcm_list=${modlist[0]}
export sc_list=${sclist[0]}
export var_list=${cmipvarlist[0]}

python3 $scriptdir'CMIP_daily_download.py'

