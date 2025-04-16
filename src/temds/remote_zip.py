import requests
import zipfile

from pathlib import Path


# __COMPRESSED_TYPES__ = ['.zip']#, '.gz']

class RemoteZipPedanticError(Exception):
    """Raise if pedantic is True and the file already exists locally"""
    pass

class RemoteZip(object):
    """
    RemoteZip is a utility class for downloading and extracting ZIP files from
    a remote URL.

    Attributes
    ----------
    url : str
        The URL of the remote ZIP file.
    local_file : pathlib.Path or None
        The local file path where the ZIP file is downloaded.
    verbose : bool
        If True, enables verbose output for debugging purposes.
    pedantic : bool
        If True, raises an error if the local file already exists during
        download.

    """
    def __init__(self, url, verbose=False, pedantic=False):
        ''' Initializes the RemoteZip object with the given URL and optional
        verbosity and pedantic flags.'''
        self.url = url
        self.local_file = None
        self.verbose = verbose
        self.pedantic=pedantic

    def download(self, location, overwrite=False):
        """
        Downloads a file from the specified URL to the given location.

        Parameters
        ----------
        location : str or Path
            The directory where the file will be downloaded.
        overwrite : bool, optional
            If True, overwrites the file if it already exists. Default is False.

        Returns
        -------
        Path
            The path to the downloaded file.

        Raises
        ------
        RemoteZipPedanticError
            If `pedantic` is True and the file already exists locally.

        Notes
        -----
        - Creates the specified directory if it does not exist.
        - Prints verbose messages if `verbose` is True.
        """

        location = Path(location)
        self.local_file = Path(location, Path(self.url).name)
        
        if not self.local_file.exists() or overwrite:
            if self.verbose: print(f"downloading: {self.url}" )
            location.mkdir(parents=True, exist_ok=True)

            r = requests.get(self.url)
            with self.local_file.open('wb') as new_file:
                new_file.write(r.content)
        else:
            if self.verbose:
                print(f"Local file exists {self.local_file}" )
            if self.pedantic:
                raise RemoteZipPedanticError(
                    f"Local file exists {self.local_file}"
                )

        return self.local_file

    # def uncompress(self):
    #     if self.local_file is None:
    #         return 0# to exception

    #     if not self.local_file.suffix in __COMPRESSED_TYPES__:
    #         return self.local_file


    #     if self.local_file.suffix == '.zip':
    #         return self.unzip()
    def unzip(self, where = None):
        """
        Extracts the contents of a zip file to a specified directory.

        Parameters
        ----------
        where : str or Path, optional
            The directory where the contents of the zip file should be 
            extracted. If not provided, the contents will be extracted to a 
            directory with the same name as the zip file (without the extension) 
            in the same location as the zip file.

        Returns
        -------
        Path
            The path to the directory where the contents were extracted, or 0 
            if the `local_file` attribute is None.

        Raises
        ------
        zipfile.BadZipFile
            If the file is not a valid zip file.
        FileNotFoundError
            If the zip file does not exist.

        Notes
        -----
        - The method assumes that `self.local_file` is a Path object pointing 
          to the zip file.
        - If `self.verbose` is True, progress messages will be printed to the 
          console.
        """

        if self.local_file is None:
            return 0# to exception
        if self.verbose: print(f"Extracting {self.local_file}")
        with zipfile.ZipFile(self.local_file, 'r') as zip_ref:
          if where is None:
            where = Path(self.local_file.parent, self.local_file.stem)
          if self.verbose: print(f"Extracting {where=}")
          zip_ref.extractall(where)
        return where
    

    