# 
## ERA5 qdm demo for cli

REGION="H07_V16"
REGION_DIR=./working/03-tiles-testing/$REGION
REGION_LAYER_IDX=110 # have to look this up currently

TILE_INDEX=working/00-aoi/tile-index-annotated/
MASK=working/00-aoi/aoi-5km-buffer-6931.tif

create Region
echo "creating region $REGION"
TEMdownscale --overwrite region create $REGION_DIR $TILE_INDEX\
    --mask=$MASK --resolution=4000 --layer=$REGION_LAYER_IDX

echo ""
echo 'importing era5-daily'
TEMdownscale --parallel --n-process=12 --no-load-all region import-data \
    $REGION_DIR ./working/02-arctic/era5-daily 'era5-daily'


echo ""
echo '... checking spatial mask'
TEMdownscale --use-region=$REGION_DIR --parallel --n-process=12 \
    --load-item=era5-daily preprocess check-spatial-mask era5-daily

status=$?
if [ $status != 0 ]; then 
    echo "Exiting check your data"
    exit 1
fi 

echo ""
echo '... checking number days'
TEMdownscale --use-region=$REGION_DIR --parallel --n-process=12 \
    --load-item=era5-daily preprocess check-number-days era5-daily

status=$?
if [ $status != 0 ]; then 
    echo "Exiting check your data"
    exit 1
fi 


echo ""
echo '... fill outliers'
TEMdownscale --overwrite --use-region=$REGION_DIR --parallel --n-process=12 \
    --load-item=era5-daily preprocess fill-outliers era5-daily

echo '... fill oob'
TEMdownscale --overwrite --use-region=$REGION_DIR --parallel --n-process=12 \
    --load-item=era5-daily preprocess fill-oob era5-daily nirr 0 lower

TEMdownscale --overwrite --use-region=$REGION_DIR --parallel --n-process=12 \
    --load-item=era5-daily preprocess fill-oob era5-daily prec 0 lower

TEMdownscale --overwrite --use-region=$REGION_DIR --parallel --n-process=12 \
    --load-item=era5-daily preprocess fill-oob era5-daily vapo 0 lower

TEMdownscale --overwrite --use-region=$REGION_DIR --parallel --n-process=12 \
    --load-item=era5-daily preprocess fill-oob era5-daily tair_avg -100 lower

TEMdownscale --overwrite --use-region=$REGION_DIR --parallel --n-process=12 \
    --load-item=era5-daily preprocess fill-oob era5-daily tair_avg 50 upper



# Import worlclim
echo ""
echo 'importing worldclim'
TEMdownscale --use-region=$REGION_DIR --no-load-all preprocess worldclim \
    "" working/01-download/worldclim/ ""


## import cru-jra
echo ""
echo 'importing cru'
TEMdownscale --parallel --n-process=12 --no-load-all region import-data \
    $REGION_DIR ./working/02-arctic/cru-jra-standard/ 'crujra-daily'


echo ""
echo 'Calculating era5 baseline'
TEMdownscale \
    --use-region=$REGION_DIR --load-item=era5-daily\
    statistics calculate-normals "" era5-daily 1970 2000 era5-baseline


echo ""
echo 'calculation era5 corrections'
TEMdownscale --use-region=$REGION_DIR --parallel --n-process=12 \
    --load-item=era5-daily --load-item=worldclim --load-item=era5-baseline\
    preprocess era5-corrections era5-daily era5-baseline worldclim era5-corrections

echo ""
echo 'Downscaling'
TEMdownscale --use-region=$REGION_DIR --parallel --n-process=12 \
    --load-item=crujra-daily --load-item=era5-corrections \
    downscale qdm-method downscaled-qdm crujra-daily era5-corrections \
    1950 2020 1901 1949

    # --observed-period 1950 2020 --simulated-period 1901 1949
