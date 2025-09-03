"""
Topo
---------

Metadata for topographic dataset

See: for dataset details 
"""

NAME = 'topo'


# citation for topo  dataset
CITATION = ()

url = 'https://edcintl.cr.usgs.gov/downloads/sciweb1/shared/topo/downloads/GMTED/Grid_ZipFiles/mn75_grd.zip'

raw_file = 'mn75_grd'

unzipped_raw = 'mn75_grd'

processed = 'working/06-ancillary/elevation_250m_4326.tif'

class TopoURLError(Exception):
    """Raised if the url cannot be formatted"""
    pass

