#!/usr/bin/env python

import textwrap
import subprocess
import tempfile
import os
#from io import StringIO
import asyncio



async def async_run(cmd):
  '''
  Inspired from here:
  https://towardsdatascience.com/deep-dive-into-multithreading-multiprocessing-and-asyncio-94fdbe0c91f0
  '''
  print(f"In async run(..) Creating subprocess shell for  {cmd=}")
  proc = await asyncio.create_subprocess_shell(
      cmd,
      stdout=asyncio.subprocess.PIPE,
      stderr=asyncio.subprocess.PIPE)

  stdout, stderr = await proc.communicate()

  print(f'[{cmd!r} exited with {proc.returncode}]')
  if stdout:
      print(f'[stdout]\n{stdout.decode()}')
  if stderr:
      print(f'[stderr]\n{stderr.decode()}')



class CloudShellBucketFiller(object):
  '''
  This class allows for running code on the Google Cloud Shell, which is an
  ephemeral VM provided as part of the GCP. This is a funky arrangement
  in that we are passing computation off to the cloud shell environment rather
  than running it locally, but there are some limitations and awkwardness in 
  how scripting the actions on the cloud shell...at some point it feels like
  there might be security issues?
  
  The idea is that we are using the ephemeral Cloud Shell VM as a conduit for
  downloading data direct to a bucket. So on the cloud shell, (whcih comes 
  provisioned with all the handy gcloud utilities), we mount a bucket as a drive
  and then run the download directly to that drive. As far as I can tell the 
  data doesn't touch the local file system of the Cloud Shell instance, which
  is good becuase it is pretty limited.

  The other alternatives are:
  1) Download data from cru (or wherever) to local machine and then upload to 
     bucket.
  2) Use dedicated VM to download data to the VM and then move it to a bucket
     (or use the fuse mounted bucket)
  3) clone/install python code to the VM (or cloud shell) and run the commands
     there rather than using this "pass thru" CloudShellBucketFiller object.

  Overall this is sort of funky and I am not sure how useful, so a bunch of the 
  methods are stubbed out and I am not sure if it is worth finishing them...
  '''

  def __init__(self, root):
    
    self.root = root

    self.BUCKET = 'cru-25-jra'


  def gcp_auth(self):
    #??? do we need this here? WIll it work?
    subprocess.run('gcloud auth login'.split(' '))

  def gcp_shell(self):
    pass


  def mount_bucket(self):
    pass


  def get_file():
    pass

  def setup_creds(self):
    '''
    Might be able to make this way simpler by making creds locally and then
    just copying up the ~/.config folder??
    '''
    uname = os.environ['CEDA_UNAME']
    cedapw = os.environ['CEDA_PW']

    # Make a script file that will be run on the remote cloud shell
    code_str = textwrap.dedent(f'''\n
    export CEDA_USERNAME={uname}
    export CEDA_PASSWORD={cedapw}
    mkdir ~/ceda_pydap_cert_code
    cd ~/ceda_pydap_cert_code
    git clone https://github.com/cedadev/online_ca_client
    cd online_ca_client/contrail/security/onlineca/client/sh/
    ./onlineca-get-trustroots-wget.sh -U https://slcs.ceda.ac.uk/onlineca/trustroots/ -c ~/trustroots -b
    ./onlineca-get-cert-wget.sh -U  https://slcs.ceda.ac.uk/onlineca/certificate/ -c ~/trustroots -l {uname} -o $PWD/creds.pem
    ''')

    # copy the script file up to the cloud instance
    code = tempfile.NamedTemporaryFile(mode='w+') # <- helps for writing string
    code.write(code_str)
    code.flush()
    subprocess.run(['gcloud', 'cloud-shell', 'scp',  f'localhost:{code.name}', 'cloudshell:~/setup_cred.sh'])

    print("Copied the file up, now trying to run it...")
    # run the script file
    subprocess.run(['gcloud', 'cloud-shell', 'ssh', '--command', 'bash setup_cred.sh'])



  def refresh_creds(self):
    uname = os.environ['CEDA_UNAME']
    cedapw = os.environ['CEDA_PW']

    code_str = textwrap.dedent(f'''\n
    export CEDA_USERNAME={uname}
    export CEDA_PASSWORD={cedapw}
    cd ~/ceda_pydap_cert_code/online_ca_client/contrail/security/onlineca/client/sh/
    echo $CEDA_PASSWORD | ./onlineca-get-cert-wget.sh -U  https://slcs.ceda.ac.uk/onlineca/certificate/ -c ~/trustroots -l {uname} -o $PWD/creds.pem -S
    ''')

    code = tempfile.NamedTemporaryFile(mode='w+') # <- helps for writing string
    code.write(code_str)
    code.flush()

    subprocess.run(['gcloud', 'cloud-shell', 'scp',  f'localhost:{code.name}', 'cloudshell:~/auto_cred_refresh.sh'])

    # WORKS
    #print( subprocess.run(['gcloud', 'cloud-shell', 'ssh', '--command', "export CEDA_USERNAME=ctobey && echo $CEDA_USERNAME"]) )

    # WORKS
    subprocess.run('gcloud cloud-shell ssh --command ls'.split(' '))
    
    subprocess.run(['gcloud', 'cloud-shell', 'ssh', '--command', 'bash auto_cred_refresh.sh'])

  def download_file(self, var='tmax', year=1901):

    MOUNT_POINT = 'cru-jra-25'

    # check bucket is already mounted...
    cp = subprocess.run(
      [
        'gcloud', 'cloud-shell', 'ssh', '--authorize-session', '--command',
        f'mount | grep {MOUNT_POINT}'
      ], 
      capture_output=True
    )
    #print(cp.stdout.decode('utf-8'))


    if not cp.stdout.decode('utf-8'):
      subprocess.run([
        'gcloud', 'cloud-shell', 'ssh', '--authorize-session', '--command',
        f'gcsfuse {MOUNT_POINT} {MOUNT_POINT}'
      ])
    else:
      print("Bucket is already mounted...")

    print(subprocess.run(['gcloud', 'cloud-shell', 'ssh', '--authorize-session', '--command', f'ls {MOUNT_POINT}']))

    cp = subprocess.run([
      'gcloud','cloud-shell','ssh', '--authorize-session', '--command',
      f"cd {self.root}/{MOUNT_POINT} && export CEDA_USERNAME={os.environ['CEDA_UNAME']} && export CEDA_PASSWORD={os.environ['CEDA_PW']} && wget --certificate ~/ceda_pydap_cert_code/online_ca_client/contrail/security/onlineca/client/sh/creds.pem -e robots=off --mirror --no-parent -r http://dap.ceda.ac.uk/thredds/fileServer/badc/cru/data/cru_jra/cru_jra_2.5/data/{var}/crujra.v2.5.5d.{var}.{year}.365d.noc.nc.gz",
      
    ])
      #http://dap.ceda.ac.uk/thredds/fileServer/badc/cru/data/cru_jra/cru_jra_2.5/data/{var}/crujra.v2.5.5d.{var}.{year}.365d.noc.nc.gz',
      #https://dap.ceda.ac.uk/badc/cru/data/cru_jra/cru_jra_2.5/data/tmin/crujra.v2.5.5d.tmin.1901.365d.noc.nc.gz?download=1
    #])


  ### NOTE: Need method to check for active gcloud configuration!!


  def super_dl(self, var_list, year_list):

    # need to check if bucket is mounted!
    # seems that the download from ceda to this cloud shell is much faster than to the mounted bucket...

    loop = asyncio.new_event_loop()
    async def create_task_func(year_list=year_list):
      tasks = list()
      for var in var_list:
        for year in year_list:
          print(f"Making task to get file for {var=} {year=}")
          uname = os.environ['CEDA_UNAME']
          cedapw = os.environ['CEDA_PW']
          tasks.append(asyncio.create_task(async_run(f'gcloud cloud-shell ssh --authorize-session --command "cd {self.root}/cru-jra-25 && export CEDA_USERNAME={uname} && export CEDA_PASSWORD={cedapw} && wget --certificate ~/ceda_pydap_cert_code/online_ca_client/contrail/security/onlineca/client/sh/creds.pem -e robots=off --mirror --no-parent -r http://dap.ceda.ac.uk/thredds/fileServer/badc/cru/data/cru_jra/cru_jra_2.5/data/{var}/crujra.v2.5.5d.{var}.{year}.365d.noc.nc.gz"')))
      await asyncio.wait(tasks)

    loop.run_until_complete(create_task_func())
    loop.close()


# import asyncio
# async def func(num):
#     print('Starting func {0}...'.format(num))
#     await asyncio.sleep(0.1)
#     print('Ending func {0}...'.format(num))

# loop = asyncio.get_event_loop()
# async def create_tasks_func():
#     tasks = list()
#     for i in range(5):
#         tasks.append(asyncio.create_task(func(i)))
#     await asyncio.wait(tasks)
# loop.run_until_complete(create_tasks_func())
# loop.close()


