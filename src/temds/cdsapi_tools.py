"""
CDS API Tools
-------------

tools for downloading CDS API data(i.e. era5, cmip6)
"""
from pathlib import Path

from ecmwf.datastores import Client

def get_client():
    """Get default config of ECMWF client

    Parameters
    ----------
    """
    return Client(progress=False, cleanup=True, sleep_max=10)

def download(where: Path, collection_id: str,  request: dict):
    """download from ECMWF 

    Parameters
    ----------
    where: Path
        path to save file at
    collection_id: str
        api collection
    request: dict
        api request
    """
    client = get_client()
    client.retrieve(collection_id, request, target=where) 

