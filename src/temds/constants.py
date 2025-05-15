"""
Global Constant Definitions
---------------------------
"""
import numpy as np


## unit related constants
ZERO_C_IN_K = 273.15 # degrees kelvin
SECONDS_PER_DAY = 24 * 60 * 60


## calendar related constants
## we assume 365 day years
DAYS_PER_MONTH = np.cumsum([31,28,31,30,31,30,31,31,30,31,30,31]) 
MONTH_START_DAYS =  np.append([1], (DAYS_PER_MONTH + 1) )[:-1] 


def get_month_slice(mn): 
    """Utility Function to convert DAYS_PER_MONTH ,and MONTH_START_DAYS
    to a slice that can be used to index daily data

    Parameters
    ----------
    mn: int
        a 0 based month number

    Returns
    -------
    slice 
    """
    # - 1 for zero based adjustment
    return slice(MONTH_START_DAYS[mn]-1, DAYS_PER_MONTH[mn])