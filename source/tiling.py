#!/usr/bin/env python

import subprocess

import AOIMask

TILE_SIZE_X = 100
TILE_SIZE_Y = 100


def calculate_tile_gridsize():
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



def calculate_tile_extents():

  aoimask = AOIMask.AOIMask()
  aoimask.load_from_raster('working/aoi_5km_buffer_6931.tiff')
  
  maskX, maskY = aoimask.size()

  aoi_extents = aoimask.extents()
  #aoi_extents = aoimask.bounds()
  aoiGT = aoimask.geoTransform()


  #msk_all_left=$(echo ${msk_all_o[0]} | bc)
  #msk_all_bottom=$(echo ${msk_all_o[1]}+${msk_all_res[1]}*${msk_all_sz[1]} | bc)
  #msk_all_top=$(echo ${msk_all_o[1]} | bc)
  #msk_all_right=$(echo ${msk_all_o[0]}+${msk_all_res[0]}*${msk_all_sz[0]} | bc)
  #ext_all_6931=($msk_all_left $msk_all_bottom $msk_all_right $msk_all_top)

  #${msk_all_o[@]}  #   -4602000.000000000000000  4251000.000000000000000  <-- minx, maxy
  #${msk_all_sz[@]} #     2242 1934
  #${msk_all_res[@]}   #   4000.000000000000000 -4000.000000000000000


  maL = aoi_extents['minx']
  maB = aoi_extents['miny'] + -4000 * maskY
  maT = aoi_extents['maxy']
  maR = aoi_extents['minx'] + 4000 * maskX
  HG_ext = (maL, maB, maR, maT)

  N_tiles_X, N_tiles_Y = calculate_tile_gridsize()

  tile_extents = []

  for h in range(N_tiles_X):
    for v in range(N_tiles_Y):

      tile_xmin = aoi_extents['minx'] + TILE_SIZE_X * h * aoiGT[1]
      if (h+1) == len(range(N_tiles_X)):
        tile_xmax = tile_xmin + (maskX % TILE_SIZE_X) * aoiGT[1]
      else:
        tile_xmax = tile_xmin + TILE_SIZE_X * aoiGT[1]

      print("/////////////////////////////////////")
      print(aoi_extents['miny'] + -4000 * maskY)        # bottom (south) of first tile
      print(TILE_SIZE_Y * v * aoiGT[1])                 # <-- the number of meters from the bottom 
      print("\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\")

      tile_ymin = (aoi_extents['miny'] + -4000 * maskY) + TILE_SIZE_Y * v * aoiGT[1] # <---WTF?? bug?
      #tile_ymin = maB + TILE_SIZE_Y * v * aoiGT[1] # <---WTF?? bug?
      #tile_ymin = aoi_extents['miny'] + TILE_SIZE_Y * v * aoiGT[5]
      if (v+1) == len(range(N_tiles_Y)):
        tile_ymax = tile_ymin + (maskY % TILE_SIZE_Y) * aoiGT[1]
      else:
        tile_ymax = tile_ymin + TILE_SIZE_Y * aoiGT[1]

      tile_extents.append(dict(hidx=h, vidx=v, 
                               xmin=tile_xmin, xmax=tile_xmax, 
                               ymin=tile_ymin, ymax=tile_ymax))

  return tile_extents


def cut_tile(tiledict):
  

  xmin = tiledict['xmin']  
  ymin = tiledict['ymin']  
  xmax = tiledict['xmax']  
  ymax = tiledict['ymax']  
  hidx = tiledict['hidx']
  vidx = tiledict['vidx']
  #**(tiledict)

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


  # layer_name = 'aoi_5km_buffer_6931'
  # RES = str(4000)
  # target_extents = get_AOI_extents('working/aoi_5km_buffer_6931/aoi_5km_buffer_6931.shp')

  # target_extents = [str(int(x)) for x in target_extents]
  # args = ['gdal_rasterize',
  #         '-l', layer_name,
  #         '-burn', str(1),
  #         '-tr', RES, RES,
  #         '-a_nodata', str(0),
  #         '-te', *(target_extents),
  #         '-ot', 'Int16',
  #         '-of', 'GTiff',
  #         'working/aoi_5km_buffer_6931/aoi_5km_buffer_6931.shp',
  #         'working/aoi_5km_buffer_6931.tiff'
  #         ]
  # print(args)
  # subprocess.run(args)





    # # Vertical indices
    # v0=$(($v-1))
    # ymin=$(echo $msk_all_bottom+$npy*$v0*${msk_all_res[0]} | bc)
    # if [[ $v == $(printf '%.0f\n' ${ntiley}) ]]; then
    #   ymax=$(echo $ymin+$mody*${msk_all_res[0]} | bc)
    # else	
    #   ymax=$(echo $ymin+$npy*${msk_all_res[0]} | bc)
    # fi



