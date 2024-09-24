### Author: Hélène Genet, hgenet@alaska.edu 
### Institution: Arctic Eco Modeling
### Team, Institute of Arctic Biology, University of Alaska Fairbanks 
### Date: September 23 2024 
### Companion script: create_mask.py 
### Description: These scripts will produce a geotif delineating the area 
### of interest for the model simulations for the Permafrost Pathways 
### project. It includes the glaciated and ungraciated land of the boreal
### and arctic biome in the northern hemisphere.
### The user only need to specify the resolution (in m) of the mask to be 
### produced and the path to the directory that will store the processed 
### data. The projection of the mask is EPSG 6931 - WGS 84 / 
### NSIDC EASE-Grid 2.0 North
### Command: $ create_mask.sh


########   USER SPECIFICATION   ########

### target spatial resolution
res=4000

### directory to load, and process data to create the mask
maskdir='/Volumes/DATAII/DATA_processed/MASK/'
cd $maskdir


########   PROCESSING   ########

### load and unzip the geospatial raw data

## Create the directory to store the raw data
if [ -d $maskdir'raw_data' ]; then
	echo 'directory exists ... remove'
	rm -r $maskdir'raw_data'
fi
mkdir $maskdir'raw_data'
cd $maskdir'raw_data'


# create a directory to load the global map 
if [ -d $maskdir'raw_data/globmap' ]; then
	echo 'directory exists ... remove'
	rm -r $maskdir'raw_data/globmap'
fi
mkdir $maskdir'raw_data/globmap'
cd $maskdir'raw_data/globmap'
# download, rename and unzip the global map
#wget 'https://opendata.arcgis.com/api/v3/datasets/2b93b06dc0dc4e809d3c8db5cb96ba69_0/downloads/data?format=shp&spatialRefId=4326&where=1%3D1'
wget 'https://github.com/wmgeolab/geoBoundaries/raw/main/releaseData/CGAZ/geoBoundariesCGAZ_ADM1.zip'
for entry in $maskdir'raw_data/globmap'/*; do
  echo "$entry"
done
#mv  $maskdir'raw_data/globmap'/* $maskdir'raw_data/globmap/World_Countries_Generalized.zip'
unzip $maskdir'raw_data/globmap/'*'.zip' -d $maskdir'raw_data/globmap/'


# create a directory to load the ecoregion map 
if [ -d $maskdir'raw_data/ecomap' ]; then
	echo 'directory exists ... remove'
	rm -r $maskdir'raw_data/ecomap'
fi
mkdir $maskdir'raw_data/ecomap'
cd $maskdir'raw_data/ecomap'
# download, rename and unzip the global map
wget 'https://storage.googleapis.com/teow2016/Ecoregions2017.zip'
unzip $maskdir'raw_data/ecomap/'*'.zip' -d $maskdir'raw_data/ecomap/'



### Process the data
if [ -d $maskdir'processed_data' ]; then
	echo 'directory exists ... remove'
	rm -r $maskdir'processed_data'
fi
mkdir $maskdir'processed_data'
cd $maskdir'processed_data'


export res=$res
export globpath=$(echo $maskdir'raw_data/globmap/'*'.shp')
export ecopath=$(echo $maskdir'raw_data/ecomap/'*'.shp')
export outpath=$(echo $maskdir'processed_data')

ext=$(python3 '/Users/helenegenet/Helene/TEM/INPUT/production/script/create_mask.py')

gdal_rasterize -l aoi_5k_buff_6931 -burn 1 -tr $res $res -a_nodata 0 -te $ext -ot Int16 -of GTiff $maskdir'processed_data/aoi_5k_buff_6931.shp' $maskdir'processed_data/aoi_5k_buff_6931.tiff'



