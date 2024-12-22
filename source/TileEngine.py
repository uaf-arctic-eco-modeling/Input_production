#!/usr/bin/env python

import subprocess

import AOIMask

TILE_SIZE_X = 100
TILE_SIZE_Y = 100


class TileEngine(object):

  def __init__(self):
    print ("Instatitating a TileSet...")

  def calculate_tile_gridsize(self):
    aoimask = AOIMask.AOIMask()
    aoimask.load_from_raster('working/aoi_5km_buffer_6931.tiff')

    maskX, maskY = aoimask.size()

    N_TILES_X = int(maskX / TILE_SIZE_X)
    N_TILES_Y = int(maskY / TILE_SIZE_Y)

    if maskX % TILE_SIZE_X > 0:
      N_TILES_X += 1

    if maskX % TILE_SIZE_Y > 0:
      N_TILES_Y += 1

    return N_TILES_X, N_TILES_Y


  def calculate_tile_extents(self):
    '''
    Chop a raster up into tiles.
    Returns list of tile extent dictionaries. each dict will have x, y, minx 
    and max (projection coords) and H and V indices in the tileset.
    '''

    aoimask = AOIMask.AOIMask()
    aoimask.load_from_raster('working/aoi_5km_buffer_6931.tiff')
    
    maskX, maskY = aoimask.size()

    aoi_extents = aoimask.extents()

    aoiGT = aoimask.geoTransform()

    N_tiles_X, N_tiles_Y = self.calculate_tile_gridsize()

    tile_extents = []

    for h in range(N_tiles_X):
      for v in range(N_tiles_Y):

        tile_xmin = aoi_extents['minx'] + TILE_SIZE_X * h * aoiGT[1]
        if (h+1) == len(range(N_tiles_X)):
          tile_xmax = tile_xmin + (maskX % TILE_SIZE_X) * aoiGT[1]
        else:
          tile_xmax = tile_xmin + TILE_SIZE_X * aoiGT[1]

        # Origin LOWER LEFT
        # I think there is a potential bug here if X and Y resolution are not
        # the same...
        tile_ymin = aoi_extents['miny'] + -4000 * maskY  + TILE_SIZE_Y * v * aoiGT[1]  # origin lower left
        if (v+1) == len(range(N_tiles_Y)):
          tile_ymax = tile_ymin + (maskY % TILE_SIZE_Y) * aoiGT[1]
        else:
          tile_ymax = tile_ymin + TILE_SIZE_Y * aoiGT[1]

        # # Origin UPPER LEFT 
        # tile_ymin = aoi_extents['miny'] + TILE_SIZE_Y * v * aoiGT[5]
        # if (v+1) == len(range(N_tiles_Y)):
        #   tile_ymax = tile_ymin + (maskY % TILE_SIZE_Y) * aoiGT[5]
        # else:
        #   tile_ymax = tile_ymin + TILE_SIZE_Y * aoiGT[5]

        tile_extents.append(dict(hidx=h, vidx=v, 
                                xmin=tile_xmin, xmax=tile_xmax, 
                                ymin=tile_ymin, ymax=tile_ymax))

    return tile_extents    

  def cut_tileset(self, tile_extents):
    '''Given a list of tile extents, call gdal warp and actually crop out
    the tile from the raster.'''
    for tile in tile_extents:
      xmin = tile['xmin']  
      ymin = tile['ymin']  
      xmax = tile['xmax']  
      ymax = tile['ymax']  
      hidx = tile['hidx']
      vidx = tile['vidx']

      args = [
        'gdalwarp',
        '-overwrite',
        '-of', 'GTiff',
        '-r', 'bilinear',
        '-s_srs', 'EPSG:6931',
        '-t_srs', 'EPSG:6931',
        '-tr', '4000', '-4000',
        '-te', f'{xmin}', f'{ymin}', f'{xmax}', f'{ymax}',
        'working/aoi_5km_buffer_6931.tiff', f'/tmp/H{hidx}_V{vidx}.tiff'
      ]
      print(' '.join(args))
      subprocess.run(args)


  def register_tileset():
    '''Inspect a file hirearchy'''
    pass