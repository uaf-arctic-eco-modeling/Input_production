import geopandas as gp
import numpy as np
import os

# Creates area of interest. Produces extent of area of interest. 
# Starts with global maps, (two datasets) and combines them, then 
# Basically combining two datasets so that the glaciated areas are included in
# the AOI. Then buffer it by 5km (to smooth out rough coastlines, etc)
#
# Then finally make this one merged shapefile and print the extents to stdout.

### Output directory
outdir = os.getenv('outpath')

### Target resolution
res = int(os.getenv('res'))

### Read in the original shapefiles
glob = gp.read_file(os.getenv('globpath'))
eco = gp.read_file(os.getenv('ecopath'))
#glob.crs
#eco.crs

### Extract the boreal and tundra biome, without Antartica tundra, and save it to a separate file.
eco.BIOME_NAME.unique()
eco_north = eco[((eco['BIOME_NAME'] == 'Tundra') | (eco['BIOME_NAME'] == 'Boreal Forests/Taiga')) & ((eco['REALM'] != 'Antarctica') & (eco['REALM'] != 'Australasia'))]
eco_north2 = eco_north.dissolve()

### Extract Alaska and Greenland from this map and save to a separate shape file
ak_grl = glob[(glob['shapeName'] == 'Alaska') | (glob['shapeGroup'] == 'GRL')]
ak_grl2 = ak_grl.dissolve()
ak_grl2 = ak_grl2.to_crs(eco.crs)

### Merge the two shapefiles (with the same crs)
union = eco_north2.union(ak_grl2, align=True)
union.to_file(os.path.join(outdir,'aoi_4326.shp'))

### Transform to desired projection
union_t = union.to_crs(6931)
union_t.to_file(os.path.join(outdir,'aoi_6931.shp'))

### Add a 5km buffer zone
union_t5 = union_t.buffer(1.25*res)
union_t5.tmp = 1
union_t5.to_file(os.path.join(outdir,'aoi_5k_buff_6931.shp'))

### Get the extent of the shapefile
ext = union_t5.geometry.bounds
ext
minx = int(np.ceil(ext['minx']/1000))*1000
miny = int(np.ceil(ext['miny']/1000))*1000
maxx = int(np.ceil(ext['maxx']/1000))*1000
maxy = int(np.ceil(ext['maxy']/1000))*1000

### Modify the extent to be multipliers of the resolution
maxx2 = maxx + (res-(maxx - minx)%res)
maxy2 = maxy + (res-(maxy - miny)%res)

print(str(minx) + ' ' + str(miny) + ' ' + str(maxx2) + ' ' +  str(maxy2))



