#!/usr/bin/env python3

from temds.pipeline import Pipeline
from temds.logger import Logger

# Setup logger
log = Logger(level='DEBUG')

# Load and run pipeline from configuration file
# This replaces ~150 lines of manual code with automatic caching!
pipeline = Pipeline.from_config_file('examples/pipeline_temrs.yaml', logger=log)

# Run the full pipeline (or use filters like from_step, only_step, etc.)
pipeline.run()

log.info("Pipeline complete! See working/ directory for outputs.")
