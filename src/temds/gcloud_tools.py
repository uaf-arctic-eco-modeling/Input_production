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

def authorize(token=Path('token.json'), credentials = Path("credentials.json"), scopes=DEFAULT_SCOPES, overwrite=False):
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

def list_files(credentials, parent_id, limit=10):
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

def download_file(credentials, file_id, outfile, show_status=False):


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
