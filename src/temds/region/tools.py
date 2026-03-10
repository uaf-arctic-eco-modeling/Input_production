"""
"""


import numpy as np
import geopandas as gpd
import shapely
from osgeo import ogr, osr



def align_to_resolution(vector, resolution):
    
    minx, miny, maxx, maxy = vector.bounds.iloc[0]
    minx = resolution * np.floor(minx/resolution).astype(int)
    miny = resolution * np.floor(miny/resolution).astype(int)
    maxx = resolution * np.ceil(maxx/resolution).astype(int)
    maxy = resolution * np.ceil(maxy/resolution).astype(int)

    # This doesn't work because it makes a polygon that is the full extent,
    # but we lose the mask shape in this step. 
    aligned = gpd.GeoSeries(shapely.box(minx, miny, maxx, maxy ), [0], vector.crs)

    # So here we add it back
    d = {'item': ['mask', 'res_aligned_bounds'], 
         'geometry': [vector.geometry.iloc[0], aligned.geometry.iloc[0]]}

    return gpd.GeoDataFrame(d, crs=vector.crs)


def geopandas_to_ogr_dataset(geoseries, layer_name="layer"):
    """Convert GeoPandas GeoSeries to OGR vector dataset (in-memory)

    Parameters
    ----------
    geoseries : geopandas.GeoSeries
        The vector data to convert
    layer_name : str, default "layer"
        Name for the output layer

    Returns
    -------
    ogr.DataSource
        In-memory OGR dataset containing the vector data
    ogr.Layer
        The layer within the dataset
    """

    # Create in-memory vector dataset
    driver = ogr.GetDriverByName('Memory')
    ds = driver.CreateDataSource('')

    # Set up spatial reference
    srs = None
    if geoseries.crs is not None:
        srs = osr.SpatialReference()
        srs.ImportFromWkt(geoseries.crs.to_wkt())

    # Determine geometry type from first geometry
    first_geom = geoseries.iloc[0]
    geom_type_map = {
        'Point': ogr.wkbPoint,
        'LineString': ogr.wkbLineString,
        'Polygon': ogr.wkbPolygon,
        'MultiPoint': ogr.wkbMultiPoint,
        'MultiLineString': ogr.wkbMultiLineString,
        'MultiPolygon': ogr.wkbMultiPolygon,
    }

    geom_type = geom_type_map.get(first_geom.geom_type, ogr.wkbUnknown)

    # Create layer
    layer = ds.CreateLayer(layer_name, srs, geom_type)

    # Add features to layer
    for idx, geom in geoseries.items():
        feature = ogr.Feature(layer.GetLayerDefn())

        # Convert shapely geometry to OGR
        ogr_geom = ogr.CreateGeometryFromWkt(geom.wkt)
        feature.SetGeometry(ogr_geom)

        layer.CreateFeature(feature)
        feature = None  # Clean up reference

    return ds, layer 


def arctic_mask_from_political_and_ecoregion_maps(global_political_map, eco_region_map, crs=6931, buffer=5000):
    print(f"Opening {eco_region_map=}...")
    erm = gpd.read_file(eco_region_map)

    eco_tundra = erm[(erm['BIOME_NAME'] == 'Tundra') | (erm['BIOME_NAME'] == 'Boreal Forests/Taiga')]
    eco_north = eco_tundra[(eco_tundra['REALM'] != 'Antarctica') & (eco_tundra['REALM'] != 'Australasia')]

    # Dissolve geometries within `groupby` into single observation
    eco_north = eco_north.dissolve() 

    # Read the global map, 
    print(f"Opening {global_political_map=}...")
    gpm = gpd.read_file(global_political_map)
    ak_greenland = gpm[(gpm['shapeName']=='Alaska') | (gpm['shapeGroup']=='GRL')]
    ak_greenland = ak_greenland.dissolve()
    ak_greenland.to_crs(eco_north.crs)

    aoi = eco_north.union(ak_greenland, align=True)
    aoi = aoi.to_crs(epsg=crs)
    aoi = aoi.buffer(buffer)
    return aoi
