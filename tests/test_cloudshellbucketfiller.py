#!/usr/bin/env python

#from temds import CloudShellBucketFiller

# Not even sure how or if this should get tested using pytest on a local 
# machine...abandoning for now, but here is a snipped of code that you can
# user to interactively and manually experiment with the CloudShellBucketFiller
# class.

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