# Experimenting with workflows for generating single pixel inputs

This is an experiment for how we might generate single pixel dvmdostem inputs.

After previous input generation (see create_region_input.py in the dvm-dos-tem
repo), thinking that the most concise and reliable way to store the
specificaiton for input files is using NetCDF's "CDL" format. 

Advantages:
 - CDL is easily readable
 - can be written and read by standard netcdf command line tools
 - not relying on 3rd party library interpertation of datatypes (i.e. is an
   xarray float the same as a NetCDF float? what about a numpy float? or R?)

Disadvantages:
 - need to use `ncgen` (or similar) to generate files - not sure if it can be 
   directly done from Python?
 - many of the variables and attributes are redundant - if the files were
   generated programatically then rather than writing out the `_FillValue` for
   every file and every variable, the program could simply apply that fill value
   to every file. There is a tradeoff here as the explicitly specified files are
   easy to read and understand but tedious to maintain. The programitcally
   generated ones are less tedious to maintain, but can be header to read and
   trace
 - not sure how to reuse this process for multi pixel datasets (X & Y > 1)

# Process overview

1. (One time only) Generate CDL files from existing known good inputs. For
   example: 

   ```
   for f in $ls(good_input_folder/); 
   do
       ncdump -h "$f" > "template_$f.cdl"
   done
   ```

2. (One time only) Edit, by hand, each CDL file in a text editor to fix the
   following:
  
    - remove all extraneous spatial ref info (grid mappings, projection
      coordiinate variables)
    - modify X and Y dim sizes to 1
    - clear attributes
    - set _FillValue for all variables

The previous two steps were already done prior to this commit. The following
two steps are what you do when you want to create a new set of inputs from the
CDL templates.

3. Generate empty files (all data is set to the _FillValue) from the templates.
   Use the `make_empty_files.sh` script

4. Fill the files with your site data. Use the `fill_files.py` script and or 
   do it some other way.

# Example of usage

First start by making the files:

    $  sample_CDL_spec git:(main) ✗ ls
    CDL_spec_files      README.md           fill_files.py       make_empty_files.sh

Run the script to generate the empty files

    $  sample_CDL_spec git:(main) ✗ ./make_empty_files.sh CDL_spec_files 

See what we got - notice new "SAMPLEFILES" directory

    $  sample_CDL_spec git:(main) ✗ ls
    CDL_spec_files      README.md           SAMPLEFILES         fill_files.py       make_empty_files.sh

Change into that directory

    $  sample_CDL_spec git:(main) ✗ cd SAMPLEFILES 

Run the script that fills the files with data

    $  SAMPLEFILES git:(main) ✗ ../fill_files.py 

At this point your SAMPLEFILES directory shoudl have a complete input set. To
test it we can do a quick ``dvmdostem`` run just to make sure that all the files
are there, there is no problem loading them, and the datatypes are all ok.

## Test run

Now need to copy the stuff to the folder that is mounted as a volume in my
Docker container so that we can try running the model with this sample dataset
    
    $  SAMPLEFILES git:(main) ✗ mkdir ../../../dvmdostem-input-catalog/TEST_SAMPLE_NC_FILES 
    $  SAMPLEFILES git:(main) ✗ cp *.nc ../../../dvmdostem-input-catalog/TEST_SAMPLE_NC_FILES

Now change directories, and get into the docker container:

    $ SAMPLEFILES git:(main) ✗ cd ../../../dvm-dos-tem
    $ dvm-dos-tem git:(ac-refac) ✗ docker compose exec dvmdostem-dev bash
    
Then seutp a new working directory, pointing to the sample files we just made

    develop@add2dea83d63:/work$ setup_working_directory.py --input-data-path /data/input-catalog/TEST_SAMPLE_NC_FILES/ /data/workflows/TEST_SAMPLE_NC_FILES_RUN

Change into the running directory

    develop@add2dea83d63:/work$ cd /data/workflows/TEST_SAMPLE_NC_FILES_RUN/

Check the config file

    develop@add2dea83d63:/data/workflows/TEST_SAMPLE_NC_FILES_RUN$ cat config/config.js | grep historic-
        "hist_climate_file": "/data/input-catalog/TEST_SAMPLE_NC_FILES/historic-climate.nc",
        "hist_exp_fire_file": "/data/input-catalog/TEST_SAMPLE_NC_FILES/historic-explicit-fire.nc",

And finally run the model...

    develop@add2dea83d63:/data/workflows/TEST_SAMPLE_NC_FILES_RUN$ dvmdostem -l err
    Setting up logging...
    [err] [] Looks like CMTNUM output is NOT enabled. Strongly recommended to enable this output! Use util/outspec.py to turn on the CMTNUM output!
    [err] [PRE-RUN->Y] y: 0 x: 0 Year: 0
    [err] [PRE-RUN->Y] y: 0 x: 0 Year: 1
    [err] [PRE-RUN->Y] y: 0 x: 0 Year: 2
    [err] [PRE-RUN->Y] y: 0 x: 0 Year: 3
    [err] [PRE-RUN->Y] y: 0 x: 0 Year: 4
    [err] [PRE-RUN->Y] y: 0 x: 0 Year: 5
    [err] [PRE-RUN->Y] y: 0 x: 0 Year: 6


    