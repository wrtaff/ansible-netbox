import sys
from google_workspace_manager import get_service

drive_service = get_service('drive', 'v3')
file_metadata = {
    'name': '2026-06-08-_EP_BOD_Meeting',
    'mimeType': 'application/vnd.google-apps.folder',
    'parents': ['1iSRwlpYt-PsRO9ZPXDRXJ--WFA4AXZpQ']
}
folder = drive_service.files().create(body=file_metadata, fields='id').execute()
print(folder.get('id'))
