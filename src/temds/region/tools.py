"""
Tools
-----

Tools for region creation and manipulation
"""
import numpy as np
import geopandas as gpd
from pathlib import Path
import shapely
from osgeo import ogr, osr

from .mask import Mask
from ..logger import Logger


def align_to_resolution(vector: gpd.GeoSeries | gpd.GeoDataFrame, resolution: float | int) -> gpd.GeoSeries:
    """Align the first feature in a GeoSeries to a resolution

    Parameters
    ----------
    vector: gpd.GeoSeries | gpd.GeoDataFrame
        vector dataset with on feature
    resolution:
        crs grid unit resolution to align bounds to

    Returns
    -------
    gpd.GeoSeries
    """
    minx, miny, maxx, maxy = vector.bounds.iloc[0]
    minx = resolution * np.floor(minx/resolution).astype(int)
    miny = resolution * np.floor(miny/resolution).astype(int)
    maxx = resolution * np.ceil(maxx/resolution).astype(int)
    maxy = resolution * np.ceil(maxy/resolution).astype(int)
    aligned =  gpd.GeoSeries(shapely.box(minx, miny, maxx, maxy ), [0], vector.crs)
    return aligned


def geopandas_to_ogr_dataset(geoseries: gpd.GeoSeries, layer_name: str ="layer") -> ogr.Dataset:
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


def arctic_mask_from_political_and_ecoregion_maps(
        global_political_map: Path, 
        eco_region_map: Path,
        crs: int=6931, 
        buffer: int =5000, 
        log: Logger= Logger()
    ) -> gpd.GeoSeries:
    """Create arctic mask as GeoSeries from political map and ecoregion map

    Parameters
    ----------
    global_political_map: Path
        ... Vector file
    eco_region_map: Path
        ... Vector file
    crs: int
        EPSG crs number
    buffer: int 
        buffer in pixels
    log: Logger
        Logger object

    
    Returns
    -------
    gpd.GeoSeries
    """
    msg = f"Opening {eco_region_map=}..."
    log.info(msg)
    erm = gpd.read_file(eco_region_map)

    eco_tundra = erm[(erm['BIOME_NAME'] == 'Tundra') | (erm['BIOME_NAME'] == 'Boreal Forests/Taiga')]
    eco_north = eco_tundra[(eco_tundra['REALM'] != 'Antarctica') & (eco_tundra['REALM'] != 'Australasia')]

    # Dissolve geometries within `groupby` into single observation
    eco_north = eco_north.dissolve() 

    # Read the global map, 
    msg = f"Opening {global_political_map=}..."
    log.info(msg)

    gpm = gpd.read_file(global_political_map)
    ak_greenland = gpm[(gpm['shapeName']=='Alaska') | (gpm['shapeGroup']=='GRL')]
    ak_greenland = ak_greenland.dissolve()
    ak_greenland.to_crs(eco_north.crs)

    aoi = eco_north.union(ak_greenland, align=True)
    aoi = aoi.to_crs(epsg=crs)
    aoi = aoi.buffer(buffer)
    return aoi

def mask_boundary_compatibility_report(mask: Mask, boundary: gpd.GeoSeries | gpd.GeoDataFrame) -> tuple[bool, bool, bool]:
    """Checks the compatibility of a Mask, and the first item in a GeoSeries 
    for the purpose of creating a Region

    Parameters
    ----------
    mask: Mask
        A mask object to check
    boundary:  gpd.GeoSeries | gpd.GeoDataFrame
        A GeoSeries to check, Only the first item is checked

    Returns
    -------
    tuple[bool, bool, bool]
    """
    crs_check = boundary.crs == mask.crs

    resolution = mask.resolution
    bounds = boundary.bounds.iloc[0]
    shape_boundary= (
        int((bounds['maxx'] - bounds['minx'])//np.abs(resolution[0])),
        int((bounds['maxy'] - bounds['miny'])//np.abs(resolution[1]))
    )
    shape_mask = mask.shape

    shape_check = shape_boundary == shape_mask

    b_gt = (bounds['minx'], resolution[0], 0, bounds['maxy'], 0, resolution[1])

    gt_check = mask.transform  == b_gt

    return crs_check, shape_check, gt_check

