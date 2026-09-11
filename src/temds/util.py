#!/usr/bin/env python

import os
import pathlib
import errno
import subprocess
import xarray as xr

from osgeo import gdal

import importlib.metadata # for version lookup

historic_co2 = {
    # Manually spliced data from NOAA ESRL Global Monitoring Division
    # with the data from the demo file. (just added yrs 2016+)
    # https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_annmean_mlo.txt
    'year': list(range(1901, 2026)),
    'co2': [
        296.311, 296.661, 297.04, 297.441, 297.86, 298.29, 298.726, 299.163, 
        299.595, 300.016, 300.421, 300.804, 301.162, 301.501, 301.829, 302.154, 
        302.48, 302.808, 303.142, 303.482, 303.833, 304.195, 304.573, 304.966, 
        305.378, 305.806, 306.247, 306.698, 307.154, 307.614, 308.074, 308.531, 
        308.979, 309.401, 309.781, 310.107, 310.369, 310.559, 310.667, 310.697, 
        310.664, 310.594, 310.51, 310.438, 310.401, 310.41, 310.475, 310.605, 
        310.807, 311.077, 311.41, 311.802, 312.245, 312.736, 313.27, 313.842, 
        314.448, 315.084, 315.665, 316.535, 317.195, 317.885, 318.495, 318.935, 
        319.58, 320.895, 321.56, 322.34, 323.7, 324.835, 325.555, 326.55, 
        328.455, 329.215, 330.165, 331.215, 332.79, 334.44, 335.78, 337.655, 
        338.925, 340.065, 341.79, 343.33, 344.67, 346.075, 347.845, 350.055, 
        351.52, 352.785, 354.21, 355.225, 356.055, 357.55, 359.62, 361.69, 
        363.76, 365.83, 367.9, 368, 370.1, 372.2, 373.6943, 375.3507, 377.0071, 
        378.6636, 380.5236, 382.3536, 384.1336, 389.9, 391.65, 393.85, 396.52, 
        398.65, 400.83,
        404.41, 406.76, 408.72, 411.65, 414.21, 416.41, 418.53, 421.08, 424.61, 427.35
    ]
}

# TODO: source this data from the web or something? This was scraped from 
# files that H.G. prepared in the prototype phase of this project.
projected_co2 = {
    'year': list(range(2025,2101)),
    'ssp1_2_6': [
        428.1659, 430.6464, 433.067, 435.4315, 437.741, 439.9947, 442.1734, 
        444.2792, 446.298, 448.2348, 450.0896, 451.8665, 453.5652, 455.1891, 
        456.7389, 458.214, 459.6201, 460.9526, 462.209, 463.3904, 464.4979, 
        465.5303, 466.4887, 467.3741, 468.1866, 468.9274, 469.5996, 470.2072, 
        470.7577, 471.2503, 471.6859, 472.0634, 472.384, 472.6476, 472.8531, 
        473.0031, 473.0973, 473.1449, 473.1515, 473.1181, 473.0427, 472.9254, 
        472.766, 472.5636, 472.3172, 472.0275, 471.6862, 471.2896, 470.8289, 
        470.3053, 469.7187, 469.0711, 468.3625, 467.5919, 466.7623, 465.8743, 
        464.9366, 463.9585, 462.9534, 461.9204, 460.8593, 459.7682, 458.6472, 
        457.4971, 456.316, 455.1101, 453.8982, 452.6904, 451.5106, 450.3548, 
        449.222, 448.1102, 447.0164, 445.9416, 444.8828, 443.8386 ],
    'ssp2_4_5': [
        428.602, 431.6007, 434.6194, 437.6581, 440.7197, 443.8022, 446.9006, 
        450.0099, 453.1201, 456.2344, 459.3536, 462.4799, 465.6151, 468.7593, 
        471.9136, 475.0784, 478.2516, 481.4264, 484.5952, 487.7581, 490.9169, 
        494.0717, 497.2235, 500.3733, 503.5201, 506.6645, 509.7982, 512.9144, 
        516.0006, 519.0559, 522.0831, 525.0824, 528.0537, 530.9979, 533.9161, 
        536.8063, 539.6577, 542.4711, 545.2394, 547.9637, 550.6442, 553.2815, 
        555.8768, 558.4291, 560.9415, 563.4098, 565.827, 568.1793, 570.4506, 
        572.6417, 574.754, 576.7882, 578.7455, 580.6267, 582.4329, 584.1615, 
        585.8063, 587.3613, 588.8164, 590.1735, 591.4336, 592.5967, 593.6638, 
        594.6359, 595.5129, 596.2975, 597.0031, 597.6421, 598.2341, 598.7792, 
        599.2762, 599.7223, 600.1193, 600.4653, 600.7594, 601.006 ],
    'ssp3_7_0': [
        429.2326, 432.9069, 436.6482, 440.4565, 444.3338, 448.2795, 452.2863, 
        456.3494, 460.4585, 464.6147, 468.8218, 473.0809, 477.394, 481.7622, 
        486.1873, 490.6685, 495.2052, 499.792, 504.4268, 509.1086, 513.8414, 
        518.6242, 523.459, 528.3469, 533.2896, 538.2866, 543.3353, 548.4351, 
        553.5848, 558.7856, 564.0394, 569.3452, 574.7061, 580.1229, 585.5946, 
        591.1246, 596.7121, 602.3578, 608.0605, 613.8202, 619.6398, 625.5175, 
        631.4552, 637.4539, 643.5136, 649.6353, 655.819, 662.0646, 668.3723, 
        674.742, 681.1747, 687.6703, 694.231, 700.8547, 707.5434, 714.2969, 
        721.1218, 728.0186, 734.9944, 742.0482, 749.1809, 756.3937, 763.6844, 
        771.0552, 778.504, 786.0339, 793.6424, 801.3351, 809.1147, 816.9804, 
        824.9331, 832.9727, 841.0994, 849.313, 857.6147, 865.9964 ],
    'ssp5_8_5': [
        429.2942, 433.0751, 436.964, 440.9619, 445.0688, 449.2861, 453.6279, 
        458.0931, 462.6914, 467.4206, 472.2818, 477.2751, 482.4023, 487.6625, 
        493.0577, 498.5909, 504.2661, 510.0873, 516.0604, 522.1866, 528.4667, 
        534.9029, 541.4951, 548.2452, 555.1554, 562.2288, 569.4772, 576.91, 
        584.5407, 592.3684, 600.3951, 608.6208, 617.0456, 625.6713, 634.499, 
        643.5294, 652.7559, 662.1849, 671.817, 681.6551, 691.6992, 701.9532, 
        712.4174, 723.0934, 733.9845, 745.0898, 756.3957, 767.8978, 779.5768, 
        791.4379, 803.482, 815.7111, 828.1282, 840.7343, 853.5314, 866.5123, 
        879.6385, 892.8746, 906.1536, 919.4807, 932.8578, 946.2858, 959.7679, 
        973.304, 986.896, 1000.54, 1014.224, 1027.926, 1041.618, 1055.3, 
        1068.982, 1082.644, 1096.306, 1109.968, 1123.61, 1137.248
    ]
}


def nc_check(nc_file, message=''):
    '''Check that a netcdf file is valid and can be opened with xarray. If not,
    delete the file and print a warning. Sometimes we are getting corrupted
    files that can't be opened, and this is a safety check to catch those before
    they cause problems downstream.'''
    try:
      with xr.open_dataset(nc_file) as ds:
        pass
    except ValueError as e:
      print(f"Invalid netcdf file: {nc_file} {message}. Error: {e}")
      print(f"Removing file: {nc_file}")
      os.remove(nc_file)
    except FileNotFoundError as e:
      print(f"File not found: {nc_file} {message}. Error: {e}")
      # Don't try to remove a file that doesn't exist, just print the warning.

def Version():
  '''Return a version string. First try to get it from git, otherwise use the
  version from the installed package.

  This way for a developer's repo the reported version is always up to date with
  the latest commit. But for an copy of the repo that doesn't have the git
  history, (e.g. pip installed version from a shallow checkout) it will still
  report a version - the version that was packaged up.

  Even with a pip editable install, the versioningit number doesn't seem to keep
  up with the commits unless you reinstall the package. So the subprocess
  approach is still better for a developer's repo where you might make a lot of
  commits between installations (pip install -e .)

  Strange that the command line versioningit tool does manage to keep up with
  commits, but the version available through importlib.metadata.version()
  doesn't....
  '''

  try:
    # Need to check current directory, save it, and then change to the 
    # directory of the module then run the git command, then change back.
    # Otherwise if the current directory is not in the repo, git will complain.
    currentDir = os.getcwd()
    os.chdir(os.path.dirname(__file__))
    __version__ = subprocess.check_output(['git', 'describe', '--tags']).strip().decode('utf-8')
    os.chdir(currentDir)
  except subprocess.CalledProcessError as e:
    print(f"Warning: Couldn't get version from git, using installed version. {e}")
    os.chdir(currentDir)
    # Return the version string of the installed software. Managed by a special
    # tool called versioningit which is driven by git tags.
    __version__ = importlib.metadata.version("temds")

  return f"{__version__}"


def gdalGeoTransformHelp():
  '''Print some handy info.'''

  print('''
GT(0) x-coordinate of the upper-left corner of the upper-left pixel.
GT(1) w-e pixel resolution / pixel width.
GT(2) row rotation (typically zero).
GT(3) y-coordinate of the upper-left corner of the upper-left pixel.
GT(4) column rotation (typically zero).
GT(5) n-s pixel resolution / pixel height (negative value for a north-up image).
https://gdal.org/en/stable/tutorials/geotransforms_tut.html
''')

def mkdir_p(path):
  '''Provides similar functionality to bash mkdir -p'''
  try:
     os.makedirs(path)
  except OSError as exc:  # Python >2.5
    if exc.errno == errno.EEXIST and os.path.isdir(path):
      pass
    else:
      raise

def getRasterExtents(raster):
  '''
  Hackish approach to computing raster extents...
  Not sure how robust the type checking approach is...
  '''
  if type(raster) is str or type(raster) is pathlib.PosixPath:
    ds = gdal.Open(raster, gdal.gdalconst.GA_ReadOnly)
  else:
    ds = raster # assume that raster is an osgeo.gdal.Dataset

  geoTransform = ds.GetGeoTransform()
  minx = geoTransform[0]
  miny = geoTransform[3]
  maxx = minx + geoTransform[1] * ds.RasterXSize
  maxy = miny + geoTransform[5] * ds.RasterYSize

  return [minx, miny, maxx, maxy]

def buffer_extent(extent, buffer, digits=6):
    """ 
    This adds a buffer to the passed in extents. Works in degrees.
    
    parameters
    ----------
    extent: list like
        extent in [minx,maxx,miny,maxy] order
        assumes coords are in degrees
    buffer: float
        buffer in degrees
    digits: int, default 6
        number of digits to pass to round

    returns
    -------
    tuple:
        (minx,maxx,miny,maxy) in degrees
    """
    minx = round(max(extent[0] - buffer, -180.0), 6)
    maxx = round(min(extent[1] + buffer,  180.0), 6)
    
    miny = round(max(extent[2] - buffer, -90.0), 6)
    maxy = round(min(extent[3] + buffer,  90.0), 6)

    
    return (minx, maxx, miny, maxy)