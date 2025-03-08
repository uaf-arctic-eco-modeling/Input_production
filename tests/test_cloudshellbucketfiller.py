#!/usr/bin/env python



from temds import CloudShellBucketFiller

def test_1():

  bf = CloudShellBucketFiller.CloudShellBucketFiller(root = "/home/tcarman2/")
  for v in ('tmin', 'tmax',):# 'tmp', 'pre', 'dswrf', 'ugrd', 'vgrd', 'spfh', 'pres'):
    for year in range(1901, 1905):
      print(f"should get {v} {year}")
      #bf.get_var(year)


def test_2():
  cbf = CloudShellBucketFiller.CloudShellBucketFiller(root = "/home/tcarman2")
  vlist = ['ugrd', 'vgrd', 'spfh']
  yrlist = range(1901,1905)
  cbf.super_dl(vlist,yrlist) 



# INTERACTIVE SESSION...
#
# %load_ext autoreload
# %autoreload 2

# import os
# import sys

# sys.path.insert(0, "source/")
# import CloudShellBucketFiller

# print(os.environ['CEDA_UNAME'])

# cbf = CloudShellBucketFiller.CloudShellBucketFiller('/home/tcarman2/')

# cbf.refresh_creds()

# cbf.download_file(var='tmax', year=1906)