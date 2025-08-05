"""
file tools
----------

Tools for downloading, and opening various file types
"""
import zipfile
import gzip
import shutil
from pathlib import Path


import requests



def download(url: str, location: Path, overwrite: bool=False):
    """Download file at url to location

    Parameters
    ----------
    url: str
        URL for file to download
    location: Path
        directory to save the remote file in
    overwrite: bool
        If True, overwrites existing local file

    Raises
    ------
    FileExistsError:
        When overwrite is False, and local file exists

    Returns
    -------
    Path 
        to downloaded data
    """
    location = Path(location)
    local_file = location.joinpath(Path(url).name)

    if not local_file.exists() or overwrite:
        location.mkdir(parents=True, exist_ok=True)

        r = requests.get(url)
        with local_file.open('wb') as new_file:
            new_file.write(r.content)
    else:
        raise FileExistsError(
            f"Local file exists {local_file}"
        )
    return local_file

def extract_gzip(archive: Path, where: Path=None):
    """Extracts content of .gz file

    Parameters
    ----------
    archive: Path
        .zip archive
    where: Path, optional
        location to extract data at. If not provided data is extracted in same 
        directory as archive

    Returns
    -------
    Path 
        to extracted data
    """
    if where is None:
        where = Path(archive.parent, archive.stem)
    with gzip.open(archive, 'rb') as fd_arc:
        with where.open('wb') as fd_where:
            shutil.copyfileobj(fd_arc, fd_where)
    return where


def unzip(archive: Path, where: Path=None):
    """Extracts content of .zip file

    Parameters
    ----------
    archive: Path
        .zip archive
    where: Path, optional
        location to extract data at. If not provided data is extracted in same 
        directory as archive

    Returns
    -------
    Path 
        to extracted data
    """
    with zipfile.ZipFile(archive, 'r') as zip_ref:
        if where is None:
            where = Path(archive.parent, archive.stem)
        zip_ref.extractall(where)
    return where

def extract(archive, where=None, archive_type='auto'):
    """Extracts content of an archive. Can attempt to
    infer the archive type if `archive_type` is 'auto'.

    Parameters
    ----------
    archive: Path
        a compressed file.
    where: Path, optional
        location to extract data at. If not provided data is extracted in same 
        directory as archive
    archive_type: str, default 'auto'
        Can be one of the following:
            'auto': infers the archive type
            '.zip': a zip archive

    Raises
    ------
    NotImplementedError:
        Raised when archive type extraction is not implemented

    Returns
    -------
    Path 
        to extracted data
    """

    if archive_type == 'auto':
        archive_type = archive.suffix
    ## TODO: will need extra logic for .tar.gz or .tar.xz files

    if archive_type == '.zip':
        where = unzip(archive, where)
    elif archive_type == '.gz':
        where = extract_gzip(archive, where)
    else:
        raise NotImplementedError('Extract not implemented for {archive_type}')

    return where

