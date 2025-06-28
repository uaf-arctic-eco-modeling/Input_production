# TEM Input Downscaling Tools

## Table of Contents

- [Description](#Desccription)
- [Installation](#installation)


## Description

Drawing of the process. Google Drawing file, stored in Shared Drives > Input_Production > "high level workflow overview"

<img src="https://docs.google.com/drawings/d/e/2PACX-1vT7IkZXsBi6C3-BPnBnHbw28yEEGBfDkYfkm3bVOznsvSoZNq_cgy3AByhTyZYtAFgXv3BrZsvGNaIz/pub?w=2487&amp;h=1372">


## Installation

### For Development
We use conda and [minconda](https://www.anaconda.com/docs/getting-started/miniconda/install#quickstart-install-instructions) for the development environment

```
conda env create -f environment.yml
conda activate temds
pip install --editable .
```


## Use

a cli tool is installed with package.

```
TEMdownscale [sub-program] [task|data source] [CONFIG] ... 
``` 

Example 

```
TEMdownscale download worldclim my-config.yml
``` 

