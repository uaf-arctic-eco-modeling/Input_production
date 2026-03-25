"""
CMIP 6
------
metadata for cmip6 data

"""
import numpy as np
from cf_units import Unit

from .. import climate_variables 
from ..constants import SECONDS_PER_DAY

from .. import pangeo_tools


NAME = 'CMIP 6'


CITATION = (

)


## REGISTER CLIMATE VARIABLES
climate_variables.register('tair_avg', NAME, 'tas')
climate_variables.register('prec', NAME, 'pr')
climate_variables.register('nirr', NAME, 'rsds')
climate_variables.register('spfh', NAME, 'huss')
climate_variables.register('psl', NAME, 'psl')

climate_variables.register_source_unit('tair_avg', NAME, Unit('kelvin'))

## the source unit is kg m-2 s-2 which i think is the same as mm/s
## so this should work
climate_variables.register_source_unit('prec', NAME, Unit(f'{SECONDS_PER_DAY} mm'))

VARS = climate_variables.aliases_for(NAME)
SOURCE_VARS = [v for v in VARS if v not in []]

EXPERIMENTS = ['historical', 'ssp126', 'ssp245', 'ssp370', 'ssp585']
# DEFAULT_EXPERIMENTS = EXPERIMENTS
DEFAULT_ENSEMBLE = "r4i1p1f1" 
DEFAULT_MODELS=['ACCESS-CM2','MRI-ESM2-0', 'CESM2']

def callback_psl_to_vapo(dataset, logger, **kwargs):
    func_name = 'cmip6.callback_psl_to_vapo'
    elevation = kwargs['elevation']
 
    logger.info(f'{func_name}: Calculating pres from psl, elevation and, air temp')
    psl = dataset['psl']
    try:
        tas = dataset['tas'] 
    except KeyError:
        tas = dataset['tair_avg']
    pres = climate_variables.calculate_pres_from_psl(psl,tas, elevation)
    try:
        spfh = dataset['huss']
    except KeyError:
        spfh = dataset['spfh']

    logger.info(f'{func_name}: Calculating vapo kPa')
    dataset['vapo'] = climate_variables.calculate_vapo(pres, spfh)
    unit = climate_variables.CLIMATE_VARIABLES['vapo'].std_unit.name
    v_name = climate_variables.CLIMATE_VARIABLES['vapo'].name
    dataset['vapo'].attrs.update(units=unit, name=v_name)
    return dataset
    

def search_pangeo(source_model, experiment, ensemble):
    parameters = {
        "experiment_id": [experiment],
        "table_id": ["day"],
        "variable_id": climate_variables.aliases_for('CMIP 6'),
        "member_id": [ensemble],
        "source_id": [source_model],
    }
    cat = pangeo_tools.connect()
    items = pangeo_tools.search(cat, parameters).df
    return items
