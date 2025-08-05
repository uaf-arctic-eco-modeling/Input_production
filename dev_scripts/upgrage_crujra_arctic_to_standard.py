"""Script to convet crujra preprocessed arctic data to
new standard units 
"""

from temds.datasources import dataset
from temds.logger import Logger, INFO
from pathlib import Path
import sys
my_logger = Logger(verbose_levels = INFO)

try: 
    in_path = sys.argv[1]
except IndexError:
    print("call script like: python upgrade_crujra_arctic_to_standard.py path/to/crujra-arctic")


def fix(file):
    my_logger.info(f'Processing File: {file}')
    corrected = dataset.YearlyDataset.from_crujra(
        None, file, logger=my_logger, is_preprocessed=True
    )
    out_path = Path(file).parent.parent.joinpath('cru-jra-standard', file.name)
    my_logger.info(f'Saving File: {out_path}')
    corrected.save(out_path)

import joblib
with joblib.parallel_config(backend="loky", n_jobs=24, verbose=20):
    joblib.Parallel()(
        joblib.delayed(fix)(item) for item in sorted(Path(in_path ).glob('*.nc'))
    )
