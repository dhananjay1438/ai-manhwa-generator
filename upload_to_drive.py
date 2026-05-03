import argparse
import sys
from pathlib import Path
from config import settings
from google_publisher import GooglePublisher
from logger import logger

def upload_file(file_path: str, folder_path: str):
    file_path = Path(file_path)
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        sys.exit(1)

    publisher = GooglePublisher(enable_drive=True, enable_youtube=False)
    
    try:
        result = publisher.upload_to_drive(
            video_path=file_path,
            title=file_path.name,
            folder_path=folder_path
        )
        logger.info(f"Successfully uploaded {file_path.name} to Drive.")
        logger.info(f"File ID: {result.get('id')}")
        logger.info(f"Web View Link: {result.get('webViewLink')}")
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload a file to a specific Google Drive folder path.")
    parser.add_argument("file_path", help="Path to the file to upload")
    parser.add_argument(
        "--folder", 
        default=settings.google_drive_folder_path,
        help="Google Drive folder path (e.g. 'path/to/folder')"
    )
    
    args = parser.parse_args()
    upload_file(args.file_path, args.folder)
