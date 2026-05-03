import argparse
import sys
from pathlib import Path
from config import settings
from google_publisher import GooglePublisher
from logger import logger

def upload_current_series(story_dir: str = None):
    # 1. Find the latest story directory if not provided
    outputs_dir = Path("outputs")
    if not story_dir:
        folders = sorted([d for d in outputs_dir.glob("*") if d.is_dir() and (d / "story_bible.json").exists()])
        if not folders:
            logger.error("No story folders found in outputs/")
            return
        story_dir = folders[-1]
    else:
        story_dir = Path(story_dir)

    logger.info(f"Scanning for videos in: {story_dir}")

    # 2. Find all final mp4 files
    video_files = sorted(list(story_dir.glob("ep_*_final.mp4")))
    if not video_files:
        logger.info("No final video files found in the directory.")
        return

    logger.info(f"Found {len(video_files)} videos to upload.")

    # 3. Initialize Publisher
    publisher = GooglePublisher(enable_drive=True, enable_youtube=False)

    # 4. Upload each video
    for video_path in video_files:
        try:
            logger.info(f"Uploading {video_path.name}...")
            result = publisher.upload_to_drive(
                video_path=video_path,
                title=video_path.name,
                folder_path=settings.google_drive_folder_path
            )
            logger.info(f"✅ Success: {video_path.name} (ID: {result.get('id')})")
        except Exception as e:
            logger.error(f"❌ Failed to upload {video_path.name}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload all generated videos from the latest series to Google Drive.")
    parser.add_argument("--story-dir", help="Optional path to a specific story directory")
    
    args = parser.parse_args()
    upload_current_series(args.story_dir)
