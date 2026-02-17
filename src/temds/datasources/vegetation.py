
"""
Vegetation Datasource Module
------------------------------

Metadata for vegetation dataset

"""

NAME = 'vegetation'

# citation for vegetation  dataset
CITATION = ()

political_shp_path = "working/00-download/mask/geoBoundariesCGAZ_ADM1/geoBoundariesCGAZ_ADM1.shp"
eco_shp_path = "working/00-download/mask/Ecoregions2017/Ecoregions2017.shp"

land_cover_path = "working/00-download/vegetation/Jan2025_TEM_Landcover2/TEM_Landcover_V4.tif"
land_cover_classification = "working/00-download/vegetation/Jan2025_TEM_Landcover2/TEMLandcoverClassDictionary.csv"


# Old IEM map is not used...
#url_iem_veg = 'https://data.snap.uaf.edu/data/IEM/Inputs/ancillary/land_cover/v_0_4/iem_vegetation_model_input_v0_4.tif'

# Instead we have a Google Drive link to a folder from HG
#https://drive.google.com/drive/folders/15QNWuPZ-m-j_JrLogM3QzqodLaDxBtBU?usp=share_link
# That when downloaded we put in `working/00-download/vegetation/`
