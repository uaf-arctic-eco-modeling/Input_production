"""
ERA 5
-----
metadata for ERA5 data

"""
import numpy as np
from cf_units import Unit

from temds import climate_variables 

NAME = 'ERA5_DAILY'

CITATION = """
In addition to the requirements of the applicable license(s), users must:

    cite the CDS catalogue entry;
    provide clear and visible attribution to the Copernicus programme and 
    attribute each data product used;


Citing the CDS catalogue entry:
    Copernicus Climate Change Service, Climate Data Store, (2024): ERA5 
    post-processed daily-statistics on single levels from 1940 to present. 
    Copernicus Climate Change Service (C3S) Climate Data Store (CDS), 
    DOI: 10.24381/cds.4991cf48 (Accessed on DD-MMM-YYYY)

 
Attribution:

Copernicus programme:
    [Generated using/Contains modified] Copernicus Climate Change Service 
    information [year]. Neither the European Commission nor ECMWF is responsible
    for any use that may be made of the Copernicus information or data it
    contains.

Data:
    Hersbach, H., Comyn-Platt, E., Bell, B., Berrisford, P., Biavati, G.,
    Horányi, A., Muñoz Sabater, J., Nicolas, J., Peubey, C., Radu, R., 
    Rozum, I., Schepers, D., Simmons, A., Soci, C., Dee, D., Thépaut, J-N., 
    Cagnazo, C., Cucchi, M. (2023): ERA5 post-processed daily-statistics on 
    pressure levels from 1940 to present. Copernicus Climate Change Service 
    (C3S) Climate Data Store (CDS), DOI: 10.24381/cds.4991cf48 
    (Accessed on DD-MMM-YYYY)
"""

DOI = "10.24381/cds.4991cf48"

## REGISTER CLIMATE VARIABLES
climate_variables.register('tair_avg', NAME, 't2m')

climate_variables.register_source_unit('tair_avg', NAME, Unit('kelvin'))

climate_variables.register('prec', NAME, 'tp')
climate_variables.register_source_unit('prec', NAME, Unit('meters'))

climate_variables.register('nirr', NAME, 'ssrd')
climate_variables.register_source_unit('nirr', NAME, Unit('J/m^2/day'))


climate_variables.register('dewpoint', NAME, 'd2m')
climate_variables.register_source_unit('dewpoint', NAME, Unit('kelvin'))

def calculate_vapo_from_dewpoint(d2m):
    """Calculate Vapor pressure from sea level pressure and
    specific humidity
    """
    return 0.1 * 6.1078 * 10 ** ((d2m * 7.5)/(d2m + 237.3))



