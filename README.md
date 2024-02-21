# Goal

Producing daily climate data to do regional ``dvmdostem`` simulations across
circumpolar from 1901-2100.

Sourced data from 4 places:

1. **CRU-JRA** baseline daily climate info
2. **WorldClim2.1** climatology, fine scale 
3. **ERA5** validation dataset
4. **CMIP6** projected climate datasets

Goal is to make a synthesized product that is coherent across time and space and
has minimal downscaling artifacts.

# Process - high level
 
1. Define area of interest (e.g. everything N of 30 degrees; this is kinda what
   the Create_mask.txt does).
    - results in a tiff

2. Download data - approach so far has been to do a one-time download of ALL
   relevant data for ALL possible regions.
    - WorldClim is "small" navigate from html site, simple, easy to do
    - CRU-JRA is on CEDA server, create file zilla account, connect to server, and download data
    - ERA5 - see download script
    - CMIP6 - in progress

3. Resample data so that they are comparable 
  - transform and align all of the datasets, best to do thru single unique grid
    (see create_mask.cxt)




# Other notes - will clean up in future meeting.

## CRU-JRA

Name of the dataset: CRU-JRA v2.4
Name of the server: ftp.ceda.ac.uk
Software to use: Filezilla
Requirement: create an account in https://services.ceda.ac.uk/cedasite/myceda/user/ and 
set password by clicking "Configure FTP Account"
Directory of the data: /badc/cru/data/cru_jra/cru_jra_2.4/data
Source of the dataset: https://catalogue.ceda.ac.uk/uuid/38715b12b22043118a208acd61771917
Description of the data can be found here: https://dap.ceda.ac.uk/badc/cru/data/cru_jra/cru_jra_1.1/data/CRUJRA_V1.1_Read_me.txt

## WorldClim2.1
dataset: https://www.worldclim.org/data/worldclim21.html
Description of the data can be found here: Fick, S.E. and R.J. Hijmans, 
WorldClim2.1(1970-2000)
2017. WorldClim 2: new 1km spatial resolution climate surfaces for global land areas. International Journal of Climatology 37 (12): 4302-4315.


