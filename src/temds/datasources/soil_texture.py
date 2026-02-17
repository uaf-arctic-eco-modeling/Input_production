#!/usr/bin/env python



NAME = "soil_texture"

# These URLs go to a web dav directory listing and then we need to download 
# specific files from w/in the directory listings...
# See the file_tools.download_all_files(..) function

# check this out, might be able to do w/o downloads: just VRT over webdav!
# https://docs.isric.org/globaldata/soilgrids/WebDav.html#programmatical-access

urlclay='https://files.isric.org/soilgrids/latest/data_aggregated/1000m/clay/'
urlsand='https://files.isric.org/soilgrids/latest/data_aggregated/1000m/sand/'
urlsilt='https://files.isric.org/soilgrids/latest/data_aggregated/1000m/silt/'



#gfres=50000

