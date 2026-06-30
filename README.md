# TEM Input Downscaling Tools

## Table of Contents

- [Description](#Desccription)
- [Use](#Use)
- [Installation](#installation)




## Description

## Use

A command line tool is installed with the package.


```
 Usage: TEMdownscale [OPTIONS] COMMAND [ARGS]...                                                                                                                            

 Main CLI entry point for TEMDS tools                                                                                                                                       

╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --version               --no-version                  Flags if version TEMDS version should be shown. [default: no-version]                                              │
│ --log-file                                   PATH     Optional path to save log to [default: None]                                                                       │
│ --log-level                                  TEXT     Log level. Options are: INFO, DEBUG, WARN. ERROR, or NONE} [default: INFO]                                         │
│ --silent                --no-silent                   Flag to suppress printing messages to console. [default: no-silent]                                                │
│ --use-region                                 PATH     Path to a directory containing a region defined by manifest.yml [default: None]                                    │
│ --load-all              --no-load-all                 Flag to load all data for a region when --use-region is provided [default: load-all]                               │
│ --load-item                                  TEXT     Keys for items to load for region if --no-load-all is provided                                                     │
│ --parallel              --no-parallel                 Flag to enable parallel processing [default: no-parallel]                                                          │
│ --n-process                                  INTEGER  Number of parallel processes to use when --parallel is used [default: 4]                                           │
│ --overwrite             --no-overwrite                Flag to overwrite existing data [default: no-overwrite]                                                            │
│ --cleanup               --no-cleanup                  Flag to cleanup downloads by removing them [default: no-cleanup]                                                   │
│ --fail-on-warn          --no-fail-on-warn             Flag to halt program execution when a warning is generated [default: no-fail-on-warn]                              │
│ --install-completion                                  Install completion for the current shell.                                                                          │
│ --show-completion                                     Show completion for the current shell, to copy it or customize the installation.                                   │
│ --help                                                Show this message and exit.                                                                                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ region       Tools for region management                                                                                                                                 │
│ download     Tools to download data                                                                                                                                      │
│ preprocess   Tools to preprocess data                                                                                                                                    │
│ statistics   Tools to preprocess data                                                                                                                                    │
│ downscale    Tools to downscale data                                                                                                                                     │
│ export       Tools to export data to a model specific format.                                                                                                            │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
``` 


## Installation

### For Development

We use conda and [minconda](https://www.anaconda.com/docs/getting-started/miniconda/install#quickstart-install-instructions) for the development environment

```
conda env create -f environment.yml
conda activate temds
pip install --editable .
```

Drawing of the process (deprecated). Google Drawing file, stored in Shared Drives > Input_Production > "high level workflow overview"

<img src="https://docs.google.com/drawings/d/e/2PACX-1vT7IkZXsBi6C3-BPnBnHbw28yEEGBfDkYfkm3bVOznsvSoZNq_cgy3AByhTyZYtAFgXv3BrZsvGNaIz/pub?w=2487&amp;h=1372">



