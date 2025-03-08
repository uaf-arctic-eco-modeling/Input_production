#! /bin/bash
setopt interactivecomments

########   USER SPECIFICATION   ########


### Script directory
scriptdir='/Users/helenegenet/Helene/TEM/INPUT/production/script_final'
### Output directory
outdir='/Volumes/5TII/DATAprocessed/DOWNSCALING'
if [ -d $outdir ]; then
  echo "Directory exists."
else
  mkdir -p $outdir
fi
### CRU-JRA input directory
cjdir='/Volumes/5TII/DATA/CLIMATE/CRU_JRA_daily'
## time period to downscale
cjstartyr=1970
cjendyr=2023
## List of variables for the CRU_JRA dataset
cjvarlist=('tmin' 'tmax' 'tmp' 'pre' 'dswrf' 'ugrd' 'vgrd' 'spfh' 'pres')
## Monthly average or sum of the daily data?
cjvarmth=('avg' 'avg' 'avg' 'sum' 'avg' 'avg' 'avg' 'avg' 'avg')
sumlist=()
avglist=()
for (( i=0; i<${#cjvarlist[@]}; i++ )); do 
#  echo "${cjvarlist[$i]}" ; 
#  echo "${cjvarmth[$i]}" ; 
  if [[ "${cjvarmth[$i]}" == 'sum' ]]; then
    sumlist+=(${cjvarlist[$i]})
  else
    avglist+=(${cjvarlist[$i]})
  fi
done

### WORLDCLIM input directory
wcdir='/Volumes/5TII/DATA/CLIMATE/WorldClim'
## List of variables for the WORLD_CLIM dataset
wcvarlist=('tmin' 'tmax' 'tavg' 'prec' 'srad' 'wind' 'vapr')
## length of each month of year
monthlengthlist=(31 28 31 30 31 30 31 31 30 31 30 31)
### CMIP input directory
cmipdir='/Volumes/5TII/DATA/CLIMATE/CMIP'




########   PROCESSING   ########



for dir in $outdir/* ; do
  if [ -d $dir ]; then
    echo $dir

#dir='/Volumes/5TII/DATAprocessed/DOWNSCALING/H01_V05'

    ### Compute CRU-JRA [1970-2000] averages
    echo 'Compute CRU-JRA baseline....'
    mkdir $dir'/baseline'
    filelist=()
    for y in {1970..2000}; do
#      echo $y
      filelist+=($dir"/CRU_JRA/cj_"$y"_rsmpl.nc")
    done
#    echo ${filelist[*]}
    ncea -O -h ${filelist[*]} $dir'/baseline/cj_1970_2000.nc'
    ncatted -O -h -a _FillValue,,o,f,1.e+20 $dir'/baseline/cj_1970_2000.nc' $dir'/baseline/cj_1970_2000.nc'
    ncatted -O -h -a missing_value,,o,f,1.e+20 $dir'/baseline/cj_1970_2000.nc' $dir'/baseline/cj_1970_2000.nc'
    ## Monthly averages to compare with CRU-JRA
    start=0
    for m in {0..11}; do
      monthlength=${monthlengthlist[$m]}
      end=$(($start+$monthlength-1))
#      echo 'month: ' $m ', length: ' $monthlength ' start: ' $start ', end: ' $end
      ncks -O -h -d time,$start,$end $dir'/baseline/cj_1970_2000.nc' $dir'/baseline/cj_1970_2000_'$(printf "%02d" $m)'.nc'
      ncra -O -h -v $(echo ${avglist[*]} | sed 's/ /,/g') -d time,0,$(($monthlength-1)) -y avg $dir'/baseline/cj_1970_2000_'$(printf "%02d" $m)'.nc' $dir'/baseline/cj_1970_2000_'$(printf "%02d" $m)'_avg.nc'
      ncra -O -h -v $(echo ${sumlist[*]} | sed 's/ /,/g') -d time,0,$(($monthlength-1)) -y ttl $dir'/baseline/cj_1970_2000_'$(printf "%02d" $m)'.nc' $dir'/baseline/cj_1970_2000_'$(printf "%02d" $m)'_ttl.nc'
      ncks -A -h $dir'/baseline/cj_1970_2000_'$(printf "%02d" $m)'_avg.nc' $dir'/baseline/cj_1970_2000_'$(printf "%02d" $m)'_ttl.nc'
      mv $dir'/baseline/cj_1970_2000_'$(printf "%02d" $m)'_ttl.nc' $dir'/baseline/cj_1970_2000_'$(printf "%02d" $m)'.nc'
      ncap2 -O -h -s 'time[$time]='$(($start+1))';month[$time]='$(($m+1))';' $dir'/baseline/cj_1970_2000_'$(printf "%02d" $m)'.nc' $dir'/baseline/cj_1970_2000_'$(printf "%02d" $m)'.nc'
      rm $dir'/baseline/cj_1970_2000_'$(printf "%02d" $m)'_avg.nc'
      start=$(($end+1))
    done
    # Appending all the monthly outputs along the time dimension
    ncrcat -O -h $dir'/baseline/cj_1970_2000_'??'.nc' $dir'/baseline/cj_1970_2000_monthly.nc'
    ncrename -O -h -v dswrf,cj_dswrf -v pre,cj_pre -v pres,cj_pres -v spfh,cj_spfh -v tmax,cj_tmax -v tmin,cj_tmin -v tmp,cj_tmp -v ugrd,cj_ugrd -v vgrd,cj_vgrd $dir'/baseline/cj_1970_2000_monthly.nc'
    rm $dir'/baseline/cj_1970_2000_'??'.nc'


    ### Compute the correction factors
    ## Concatenate the monthly WorldClim files
    echo 'Compute correction factors....'
    ncrcat -O -h $dir'/WORLD_CLIM/wc_'??'.nc' $dir'/WORLD_CLIM/wc.nc'
    ncrename -O -h -v tmin,wc_tmin -v tmax,wc_tmax -v tavg,wc_tavg -v prec,wc_prec -v srad,wc_srad -v wind,wc_wind -v vapr,wc_vapr $dir'/WORLD_CLIM/wc.nc' 
    ## Concatenate WordClim and CRU-JRA data
    ncks -A -h $dir'/WORLD_CLIM/wc.nc' $dir'/baseline/cj_1970_2000_monthly.nc'
    ncatted -O -h -a eulaVlliF_,,d,c, $dir'/baseline/cj_1970_2000_monthly.nc' $dir'/baseline/cj_1970_2000_monthly.nc'
    ## Compute the corrections
    # computing CRU-JRA vapor pressure based on Murray, F. W. 1967. 
    # “On the Computation of Saturation Vapor Pressure.” J. Appl. Meteor. 6 (1): 203–4 ; 
    # Shaman, J., and M. Kohn. 2009. “Absolute Humidity Modulates Influenza Survival, 
    # Transmission, and Seasonality.” PNAS 106 (9): 3243–8)
    ncap2 -O -h -s'
    tair_corr_oC[$time,$lat,$lon] = float(wc_tavg - (cj_tmp - 273.15)); 
    tmin_corr_oC[$time,$lat,$lon] = float(wc_tmin - (cj_tmin - 273.15)); 
    tmax_corr_oC[$time,$lat,$lon] = float(wc_tmax - (cj_tmax - 273.15)); 
    prec_corr_mm[$time,$lat,$lon] = float(wc_prec / cj_pre); 
    vapo_corr_Pa[$time,$lat,$lon] = float((wc_vapr * 1000) / ((cj_pres * cj_spfh) / (0.622 + 0.378 * cj_spfh))); 
    nirr_corr_W_m2[$time,$lat,$lon] = float(((wc_srad * 1000) / (24 * 60 * 60)) / (cj_dswrf / (24 * 60 * 60))); 
    ws_corr_ms[$time,$lat,$lon] = float(wc_wind / sqrt(cj_ugrd^2 + cj_vgrd^2));' $dir'/baseline/cj_1970_2000_monthly.nc' $dir'/baseline/cj_1970_2000_monthly.nc'
    # cleanup
    ncks -O -h -v lat,lon,time,month,tair_corr_oC,tmin_corr_oC,tmax_corr_oC,prec_corr_mm,vapo_corr_Pa,nirr_corr_W_m2,ws_corr_ms $dir'/baseline/cj_1970_2000_monthly.nc' $dir'/baseline/cj_correction.nc'
    ncatted -O -h -a _FillValue,,o,f,1.e+20 $dir'/baseline/cj_correction.nc' $dir'/baseline/cj_correction.nc'
    ncatted -O -h -a missing_value,,o,f,1.e+20 $dir'/baseline/cj_correction.nc' $dir'/baseline/cj_correction.nc'
    ncatted -O -h -a eulaVlliF_,,d,c, $dir'/baseline/cj_correction.nc' $dir'/baseline/cj_correction.nc'


    ## Extrapolate the correction factors from monthly files to a single daily file
    # For even years
    echo 'Extrapolate from monthly to daily...'
    j=0
    for m in {0..11}; do
      monthlength=${monthlengthlist[$m]}
#      echo 'Month length' $monthlength
      for i in $(seq 1 $monthlength); do
#        echo 'day: ' $j
        ncks -O -h -d time,$m $dir'/baseline/cj_correction.nc' $dir'/baseline/cj_correction_'$(printf "%03d" $(($j+1)))'.nc'
        ncap2 -O -h -s'time[$time]='$(($j+1))';' $dir'/baseline/cj_correction_'$(printf "%03d" $(($j+1)))'.nc' $dir'/baseline/cj_correction_'$(printf "%03d" $(($j+1)))'.nc'
        j=$(($j+1))
      done
    done
    ncrcat -O -h $dir'/baseline/cj_correction_'???'.nc' $dir'/baseline/cj_correction_daily_even.nc'
    rm $dir'/baseline/cj_correction_'???'.nc'
    # For odd years
    j=0
    for m in {0..11}; do
      monthlength=${monthlengthlist[$m]}
#      echo 'Month length' $monthlength
      if [[ $m == 1 ]] && [[ $yearlength == 366 ]] ; then
        echo 'Odd year' $y
        monthlength=$(($monthlength+1))
      fi
      for i in $(seq 1 $monthlength); do
#        echo 'day: ' $j
        ncks -O -h -d time,$m $dir'/baseline/cj_correction.nc' $dir'/baseline/cj_correction_'$(printf "%03d" $(($j+1)))'.nc'
        ncap2 -O -h -s'time[$time]='$(($j+1))';' $dir'/baseline/cj_correction_'$(printf "%03d" $(($j+1)))'.nc' $dir'/baseline/cj_correction_'$(printf "%03d" $(($j+1)))'.nc'
        j=$(($j+1))
      done
    done
    ncrcat -O -h $dir'/baseline/cj_correction_'???'.nc' $dir'/baseline/cj_correction_daily_odd.nc'
    rm $dir'/baseline/cj_correction_'???'.nc'


    ### Apply the correction factors
    echo 'Apply correction factors...'
    for y in $(seq $cjstartyr $cjendyr); do
#      echo $y
      file=$dir'/CRU_JRA/cj_'$y'_rsmpl.nc'
      # determine the length of the year
      yearlength=$(ncdump -h $file | sed -n '/UNLIMITED/p' | grep -Eo '[+-]?[0-9]+([.][0-9]+[ee][+-][0-9]+)?')
#      echo $yearlength
      # store the time values in an alternative variable and set the time values similar to the correction file
      ncap2 -O -h -s'time2[$time]=time; time[time]=array(1,1,$time);' $file $dir'/CRU_JRA/cj_'$y'_corr.nc'
      if [[ $yearlength == 366 ]] ; then
#        echo 'Odd year'
        ncks -A -h $dir'/baseline/cj_correction_daily_odd.nc' $dir'/CRU_JRA/cj_'$y'_corr.nc'
      else
#        echo 'Even year'
        ncks -A -h $dir'/baseline/cj_correction_daily_even.nc' $dir'/CRU_JRA/cj_'$y'_corr.nc'
      fi
      ncap2 -O -h -s'
      year[$time] = '$y';
      doy[$time] = time;
      time[$time] = time2; 
      tair_oC[$time,$lat,$lon] = float((tmp - 273.15) + tair_corr_oC); 
      tmin_oC[$time,$lat,$lon] = float((tmin - 273.15) + tmin_corr_oC); 
      tmax_oC[$time,$lat,$lon] = float((tmax - 273.15) + tmax_corr_oC); 
      prec_mm[$time,$lat,$lon] = float(pre * prec_corr_mm); 
      vapo_Pa[$time,$lat,$lon] = float(((pres * spfh) / (0.622 + 0.378 * spfh)) * vapo_corr_Pa); 
      nirr_Wm2[$time,$lat,$lon] = float((dswrf / (6 * 60 * 60)) * nirr_corr_W_m2);
      winddir_deg[$time,$lat,$lon] = float((360/2)*(1+(ugrd/abs(ugrd)))+(180/3.14159265358979323844)*atan2(ugrd,vgrd));
      wind_ms[$time,$lat,$lon] = float(sqrt(ugrd^2 + vgrd^2) * ws_corr_ms)' $dir'/CRU_JRA/cj_'$y'_corr.nc' $dir'/CRU_JRA/cj_'$y'_corr.nc'
      ncks -O -h -v time,doy,month,year,lat,lon,tair_oC,tmin_oC,tmax_oC,prec_mm,vapo_Pa,nirr_Wm2,winddir_deg,wind_ms $dir'/CRU_JRA/cj_'$y'_corr.nc' $dir'/CRU_JRA/cj_'$y'_corr.nc'
      ncatted -O -h -a _FillValue,,o,f,1.e+20 $dir'/CRU_JRA/cj_'$y'_corr.nc' $dir'/CRU_JRA/cj_'$y'_corr.nc'
      ncatted -O -h -a missing_value,,o,f,1.e+20 $dir'/CRU_JRA/cj_'$y'_corr.nc' $dir'/CRU_JRA/cj_'$y'_corr.nc'
      ncatted -O -h -a eulaVlliF_,,d,c, $dir'/CRU_JRA/cj_'$y'_corr.nc' $dir'/CRU_JRA/cj_'$y'_corr.nc'
    done
    ncrcat -O -h $dir'/CRU_JRA/cj_'????'_corr.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a cell_methods,,d,c, $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a eulaVlliF_,,d,c, $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a long_name,doy,o,c,'day of year' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a units,doy,o,c,'day' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a missing_value,doy,o,l,-9999 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a _FillValue,doy,o,l,-9999 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a calendar,doy,o,c,'365_day' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a units,year,o,c,'year' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a long_name,year,o,c,'year' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a missing_value,year,o,l,-9999 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a _FillValue,year,o,l,-9999 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a units,month,o,c,'month' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a long_name,month,o,c,'month' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a missing_value,month,o,l,-9999 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a _FillValue,month,o,l,-9999 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a units,nirr_Wm2,o,c,'W/m2' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a long_name,nirr_Wm2,o,c,'Net incoming shortwave radiation' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a missing_value,nirr_Wm2,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a _FillValue,nirr_Wm2,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a units,prec_mm,o,c,'mm' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a long_name,prec_mm,o,c,'total precipitation' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a missing_value,prec_mm,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a _FillValue,prec_mm,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a units,tair_oC,o,c,'oC' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a long_name,tair_oC,o,c,'mean air temperature' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a missing_value,tair_oC,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a _FillValue,tair_oC,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a units,tmax_oC,o,c,'oC' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a long_name,tmax_oC,o,c,'maximum air temperature' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a missing_value,tmax_oC,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a _FillValue,tmax_oC,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a units,tmin_oC,o,c,'oC' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a long_name,tmin_oC,o,c,'minimum air temperature' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a missing_value,tmin_oC,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a _FillValue,tmin_oC,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a units,vapo_Pa,o,c,'Pa' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a long_name,vapo_Pa,o,c,'vapor pressure' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a missing_value,vapo_Pa,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a _FillValue,vapo_Pa,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a units,wind_ms,o,c,'m/s' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a long_name,wind_ms,o,c,'wind speed' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a missing_value,wind_ms,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a _FillValue,wind_ms,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a units,winddir_deg,o,c,'degree' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a long_name,winddir_deg,o,c,'wind direction' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a missing_value,winddir_deg,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a _FillValue,winddir_deg,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a long_name,time,o,c,'day of year' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a units,time,o,c,'days since 1901-1-1 0:0:0' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a missing_value,time,o,l,-9999 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a _FillValue,time,o,l,-9999 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a calendar,time,o,c,'365_day' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a long_name,lon,o,c,'x coordinate of projection' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a units,lon,o,c,'m' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a missing_value,lon,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a _FillValue,lon,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a projection,lat,o,c,'EASE-Grid 2.0 North' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a epsg,lat,o,c,'6931' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a long_name,lat,o,c,'y coordinate of projection' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a units,lat,o,c,'m' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a missing_value,lat,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a _FillValue,lat,o,f,1.e+20 $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a projection,lat,o,c,'EASE-Grid 2.0 North' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ncatted -O -h -a epsg,lat,o,c,'6931' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc'
    ### Renumber the time variable as it appears that odd years are not considered in reading epoch in python
    ncap2 -O -h -s'time[$time]=array('$(echo $(( 365*($cjstartyr - 1901) )))',1,$time);' $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_daily.nc' 


    ### Synthesize to monthly timesteps
    echo 'Synthesize to monthly timesteps...'
    monthlengthlist=(31 28 31 30 31 30 31 31 30 31 30 31)
    start=0
    for m in {0..11}; do
      monthlength=${monthlengthlist[$m]}
      end=$(($start + $monthlength - 1))
#      echo 'Month length: ' $monthlength ', start: ' $start ', end: ' $end
      ncra --mro -O -d time,$start,,365,$monthlength -v prec_mm -y ttl $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_'$(printf "%02d" $(($m+1)))'_monthly1.nc'
      ncra --mro -O -d time,$start,,365,$monthlength -v nirr_Wm2,tair_oC,tmax_oC,tmin_oC,vapo_Pa,wind_ms,winddir_deg,year -y avg $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_'$(printf "%02d" $(($m+1)))'_monthly2.nc'
      ncra --mro -O -d time,$start,,365,$monthlength -v time -y min $dir'/CRU_JRA/cj_correction_daily.nc' $dir'/CRU_JRA/cj_correction_'$(printf "%02d" $(($m+1)))'_monthly3.nc'
      ncks -A -h $dir'/CRU_JRA/cj_correction_'$(printf "%02d" $(($m+1)))'_monthly1.nc' $dir'/CRU_JRA/cj_correction_'$(printf "%02d" $(($m+1)))'_monthly2.nc' 
      ncks -A -h $dir'/CRU_JRA/cj_correction_'$(printf "%02d" $(($m+1)))'_monthly2.nc' $dir'/CRU_JRA/cj_correction_'$(printf "%02d" $(($m+1)))'_monthly3.nc'
      start=$(($end + 1))
    done
    ncrcat -O -h $dir'/CRU_JRA/cj_correction_'??'_monthly3.nc' $dir'/CRU_JRA/cj_correction_monthly.nc'
    rm $dir'/CRU_JRA/cj_correction_'??'_monthly3.nc' $dir'/CRU_JRA/cj_correction_'??'_monthly2.nc' $dir'/CRU_JRA/cj_correction_'??'_monthly1.nc'
    ncatted -O -h -a cell_methods,,d,c, $dir'/CRU_JRA/cj_correction_monthly.nc' $dir'/CRU_JRA/cj_correction_monthly.nc'
    ncatted -O -h -a eulaVlliF_,,d,c, $dir'/CRU_JRA/cj_correction_monthly.nc' $dir'/CRU_JRA/cj_correction_monthly.nc'
    # Re-ordering the time dimension
    python3 $scriptdir'/downscaling_timedim.py' $dir'/CRU_JRA/cj_correction_monthly.nc' $dir'/CRU_JRA/cj_correction_monthly2.nc'
    mv $dir'/CRU_JRA/cj_correction_monthly2.nc' $dir'/CRU_JRA/cj_correction_monthly.nc'

  fi
done


