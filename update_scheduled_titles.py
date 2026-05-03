from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.story.models import StoryBible
from google_publisher import GooglePublisher
from logger import logger
from youtube_metadata import YouTubeMetadata, save_metadata, serial_video_title


def update_scheduled_titles(
    story_dir: Path,
    title_template: str | None,
    dry_run: bool,
) -> None:
    story_dir = story_dir.resolve()
    manifest_path = story_dir / "youtube_schedule_manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing schedule manifest: {manifest_path}")

    if title_template is None:
        bible = StoryBible.model_validate_json(
            (story_dir / "story_bible.json").read_text(encoding="utf-8")
        )
        title_template = f"{bible.title} | Manhwa Recap"

    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    uploads = raw_manifest.get("scheduled_uploads", [])
    publisher = None if dry_run else GooglePublisher(
        interactive_auth=False,
        enable_drive=False,
        enable_youtube=True,
    )

    for upload in uploads:
        episode_number = int(upload["episode_number"])
        metadata_path = Path(upload["metadata_path"])
        metadata = YouTubeMetadata.model_validate_json(metadata_path.read_text(encoding="utf-8"))
        new_title = serial_video_title(title_template, episode_number)

        logger.info("Episode %d title: %s", episode_number, new_title)
        if dry_run:
            continue

        metadata.video_title = new_title
        save_metadata(metadata_path, metadata)
        upload["title"] = new_title

        assert publisher is not None
        publisher.update_youtube_metadata(
            video_id=upload["youtube_video_id"],
            title=new_title,
            description=metadata.video_description,
            tags=metadata.tags,
        )

    if not dry_run:
        manifest_path.write_text(json.dumps(raw_manifest, indent=2), encoding="utf-8")
        logger.info("Updated manifest: %s", manifest_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Rewrite already scheduled YouTube uploads to stable Part N titles."
    )
    parser.add_argument("story_dir", type=Path, help="Path to outputs/<series_timestamp>")
    parser.add_argument(
        "--title-template",
        default=None,
        help='Stable title base. Example: "My Ex Wife Dumped A Hidden Billionaire | Manhwa Recap"',
    )
    parser.add_argument("--dry-run", action="store_true", help="Show changes without API updates")
    args = parser.parse_args()

    update_scheduled_titles(
        story_dir=args.story_dir,
        title_template=args.title_template,
        dry_run=args.dry_run,
    )
