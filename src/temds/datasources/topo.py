"""
Topo
---------

Metadata for topographic dataset

See: for dataset details 
"""
from pathlib import Path

from osgeo import gdal
import numpy as np

from .. import file_tools, gdal_tools

# from .dataset import TEMDataset

NAME = 'topo'

# citation for topo  dataset
CITATION = ()

URL = 'https://edcintl.cr.usgs.gov/downloads/sciweb1/shared/topo/downloads/GMTED/Grid_ZipFiles/mn75_grd.zip'
      
# This is an ArcInfo Binary Grid format. Lots of files and folders inside...
zipped_raw = 'mn75_grd.zip'


unzipped_raw = 'mn75_grd/'


def create_elevation(
        data: gdal.Dataset, region: 'Region', alg: str = 'average'
    ):
    """Create an elevation data set for an matching a region

    Parameters
    ----------
    data: gdal.Dataset 
        elevation data in any crs/resolution
    region: region.Region
        Region to create elevation data for
    alg: str, defaults 'average'
        resampling algorithm

    Returns
    -------
    gdal.Dataset 
        elevation data
    """
    elevation = region.empty_gdal_dataset()
    gdal.Warp(elevation, data, options=gdal.WarpOptions(resampleAlg=alg))
    return elevation

def create_aspect(elevation):
    """Create aspect data set from elevation

    Parameters
    ----------
    elevation: gdal.Dataset 
        elevation data in target crs/resolution

    Returns
    -------
    gdal.Dataset 
    """
    return gdal.DEMProcessing(
        "", 
        elevation, 
        processing='aspect', 
        options=gdal.DEMProcessingOptions(
            format='MEM', 
            computeEdges=True, 
            scale=elevation.GetGeoTransform()[1], 
            )
    )


def create_slope(elevation):
    """Create slope data set from elevation

    Parameters
    ----------
    elevation: gdal.Dataset 
        elevation data in target crs/resolution

    Returns
    -------
    gdal.Dataset 
    """
    return gdal.DEMProcessing(
        "", 
        elevation, 
        processing='slope', 
        options=gdal.DEMProcessingOptions(
            format='MEM', 
            computeEdges=True, 
            slopeFormat='degree'
            )
    )

def create_tpi(elevation):
    """Create tpi data set from elevation

    Parameters
    ----------
    elevation: gdal.Dataset 
        elevation data in target crs/resolution

    Returns
    -------
    gdal.Dataset 
    """
    return gdal.DEMProcessing(
        "", 
        elevation, 
        processing='TPI', 
        options=gdal.DEMProcessingOptions(
            format='MEM', 
            computeEdges=True, 
            )
    )
    
def create_drainage_class(slope):
    """Create an drainage class data from slope

    Parameters
    ----------
    slope: gdal.Dataset 
        elevation data in target crs/resolution

    Returns
    -------
    np.array
    """
    slope_array = slope.ReadAsArray()
    return np.where( ((slope_array >= -0.05) & (slope_array <= 0.05)), 1, 0 )


    
    