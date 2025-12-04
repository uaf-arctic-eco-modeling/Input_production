"""
Google Cloud Tools
------------------

Tools for Google cloud apis
"""
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
import io



DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "https://www.googleapis.com/auth/drive.readonly"
]

DEFAULT_SEARCH_FIELDS = "nextPageToken, files(id, name, trashed, kind, mimeType)"

def authorize(
        token: Path =Path('token.json'), credentials: Path = Path("credentials.json"), 
        scopes: list = DEFAULT_SCOPES, overwrite: bool = False
    ):
    """creates authorized gcloud Credentials object, by reading existing token
    or creating a new token with scopes and credentials. Existing token is used
    unless overwrite is True.
    
    Parameters
    ----------
    token: path, defaults 'token.json'
        Path to existing or new token file
    credentials: path, defaults "credentials.json"
        gcloud credentials file
    scopes: list, defaults DEFAULT_SCOPES
        scopes for creating a new token
    overwrite: bool, default False
        If true overwrite existing token with new token

    Returns
    -------
    google.oauth2.credentials.Credentials
    """
    creds = None
    token = Path(token)
    credentials = Path(credentials)
    if overwrite and token.exists():
        token.unlink()

    if token.exists():
        creds = Credentials.from_authorized_user_file(token, scopes)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials, scopes
            )
            creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with token.open('w') as fd:
                fd.write(creds.to_json())
    return creds

def list_files(credentials: Credentials, parent_id: str, limit: int = 10):
    """create a list of file in a folder with parent_id in your 
    google drive.
    
    Parameters
    ----------
    credentials: google.oauth2.credentials.Credentials
        authorized credentials object
    parent_id: string
        id of parent folder 
    limit: int, Default 10
        number of files to list

    Returns
    -------
    list:
        list of Google drive item descriptions
    """
    service = build("drive", "v3", credentials=credentials)
    results = (
        service.files()
        .list(pageSize=limit, fields="nextPageToken, files(id, name, trashed)", q=f"'{parent_id}' in parents")
        .execute()
    )
    items = results.get("files", [])
    return_items = []
    for item in items:
      if item['trashed'] == True:
        continue
      return_items.append(item)
      
    return return_items

def download_file(credentials: Credentials, file_id: str, outfile: Path, show_status: bool = False):
    """Download file with id file_id from Google Drive.
    
    Parameters
    ----------
    credentials: google.oauth2.credentials.Credentials
        authorized credentials object
    file_id: string
        id of file on drive 
    outfile: path
        Path to save downloaded file as
    show_status: bool, Defaults False
        when True, print status messages

    """
    # create drive api client
    service = build("drive", "v3", credentials=credentials)


    # pylint: disable=maybe-no-member
    request = service.files().get_media(fileId=file_id)
    file = io.BytesIO()
    downloader = MediaIoBaseDownload(file, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        if show_status: print(f"{outfile}: Download {int(status.progress() * 100)}.")
    with open(outfile, "wb") as f:
        f.write(file.getvalue())


def trash_file(credentials: Credentials, file_id: str):
    """Move file or folder with id file_id to trash in Google Drive.
    Items will be deleted automatically after 30 days in trash

    needs scope of 'https://www.googleapis.com/auth/drive'
    
    Parameters
    ----------
    credentials: google.oauth2.credentials.Credentials
        authorized credentials object
    file_id: string
        id of file on drive 

    Returns
    -------
    dict
        api response
    """
    service = build("drive", "v3", credentials=credentials)


    body_value = {'trashed': True}

    response = service.files().update(
        fileId=file_id, body=body_value
    ).execute()

    return response

def empty_trash(credentials: Credentials):
    """
    Empties Google Drive trash

    Parameters
    ----------
    credentials: google.oauth2.credentials.Credentials
        authorized credentials object

    Returns
    -------
    dict
        api response
    """
    service = build("drive", "v3", credentials=credentials)
    return service.files().emptyTrash().execute()


def delete_file(credentials: Credentials, file_id: str):
    """Delete file or folder with id file_id in Google Drive.

    needs scope of 'https://www.googleapis.com/auth/drive'
    
    Parameters
    ----------
    credentials: google.oauth2.credentials.Credentials
        authorized credentials object
    file_id: string
        id of file on drive 

    Returns
    -------
    dict
        api response
    """
    service = build("drive", "v3", credentials=credentials)

    response = service.files().delete(
        fileId=file_id,
    ).execute()

    return response

def search(credentials: Credentials, 
           query: str, 
           fields: str = DEFAULT_SEARCH_FIELDS, 
           limit: int = 10, 
           files_or_folders: str ='both'):
    """Search for files and folders in your Google Drive with an arbitrary
    query. With `files_or_folders` argument can further filter out files
    or folders as needed.
    
    Parameters
    ----------
        credentials:  authorized credentials object
        query: string
            see https://developers.google.com/workspace/drive/api/guides/search-files
        fields:
            see https://developers.google.com/workspace/drive/api/guides/search-files
        limit: int, Default 10
            number of files to list
        files_or_folders: String, Defaults 'both'
            'files'(returns only files), 'folders'(returns only folders), or 
            'both'(returns all)

    Returns
    -------
    dict:
        api response,or filtered response with 'files' key. 
    """
    service = build("drive", "v3", credentials=credentials)
    results = (
        service.files()
        .list(pageSize=limit, fields=fields, q=query)
        .execute()
    )
    if files_or_folders == 'files':
        results['files'] = [r for r in results['files']  if 'application/vnd.google-apps.folder' != r['mimeType']]
    elif files_or_folders == 'folders':
        results['files'] = [r for r in results['files']  if 'application/vnd.google-apps.folder' == r['mimeType']]
    
    return results