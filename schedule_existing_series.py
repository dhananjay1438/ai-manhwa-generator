from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from core.llm.gemini import Gemini
from core.story.models import EpisodeChapterPlan, SeriesPlan, StoryBible
from google_publisher import GooglePublisher
from logger import logger
from models import EpisodeScript
from youtube_metadata import (
    EpisodeMetadataContext,
    MetadataGenerator,
    YouTubeMetadata,
    save_metadata,
    serial_video_title,
)

IST = ZoneInfo("Asia/Kolkata")
VIDEO_RE = re.compile(r"^ep_(?P<series>.+)_(?P<episode>\d+)_final\.mp4$")


@dataclass
class ScheduledUpload:
    episode_number: int
    video_path: str
    metadata_path: str
    youtube_video_id: str
    youtube_url: str
    publish_at: str
    title: str


def infer_series_id(story_dir: Path) -> str:
    videos = sorted(story_dir.glob("ep_*_*_final.mp4"))
    if not videos:
        raise FileNotFoundError(f"No final episode videos found in {story_dir}")

    match = VIDEO_RE.match(videos[0].name)
    if not match:
        raise ValueError(f"Could not infer series id from {videos[0].name}")
    return match.group("series")


def list_episode_videos(story_dir: Path, series_id: str) -> list[tuple[int, Path]]:
    videos = []
    for path in story_dir.glob(f"ep_{series_id}_*_final.mp4"):
        match = VIDEO_RE.match(path.name)
        if not match:
            continue
        videos.append((int(match.group("episode")), path))
    return sorted(videos)


def first_schedule_datetime(first_date: date | None) -> datetime:
    if first_date:
        return datetime.combine(first_date, time(hour=21), tzinfo=IST)

    now = datetime.now(IST)
    candidate = datetime.combine(now.date(), time(hour=21), tzinfo=IST)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def load_existing_manifest(path: Path) -> dict[int, ScheduledUpload]:
    if not path.exists():
        return {}

    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        int(item["episode_number"]): ScheduledUpload(**item)
        for item in raw.get("scheduled_uploads", [])
    }


def save_manifest(path: Path, uploads: list[ScheduledUpload]) -> None:
    path.write_text(
        json.dumps({"scheduled_uploads": [asdict(upload) for upload in uploads]}, indent=2),
        encoding="utf-8",
    )


def build_context(
    story_dir: Path,
    bible: StoryBible,
    plan: SeriesPlan,
    episode_number: int,
) -> EpisodeMetadataContext:
    script_path = story_dir / f"episode_{episode_number:02d}_script.json"
    chapter_plan_path = story_dir / f"episode_{episode_number:02d}_chapter_plan.json"
    if not script_path.exists():
        raise FileNotFoundError(f"Missing episode script: {script_path}")

    script = EpisodeScript.model_validate_json(script_path.read_text(encoding="utf-8"))
    episode_plan = next(
        episode for episode in plan.episodes if episode.episode_number == episode_number
    )

    chapters = []
    if chapter_plan_path.exists():
        chapter_plan = EpisodeChapterPlan.model_validate_json(
            chapter_plan_path.read_text(encoding="utf-8")
        )
        chapters = [chapter.title for chapter in chapter_plan.chapters]

    return EpisodeMetadataContext(
        series_title=bible.title,
        series_logline=bible.logline,
        episode_number=episode_number,
        episode_title=script.title or episode_plan.title,
        episode_summary=episode_plan.summary,
        hook_line=script.hook_line,
        cliffhanger_ending=script.cliffhanger_ending,
        chapters=chapters,
    )


async def metadata_for_episode(
    story_dir: Path,
    generator: MetadataGenerator,
    bible: StoryBible,
    plan: SeriesPlan,
    episode_number: int,
    series_title_template: str,
    force_title: bool,
) -> tuple[YouTubeMetadata, Path]:
    metadata_path = story_dir / f"episode_{episode_number:02d}_youtube_metadata.json"
    if metadata_path.exists():
        metadata = YouTubeMetadata.model_validate_json(metadata_path.read_text(encoding="utf-8"))
        expected_title = serial_video_title(series_title_template, episode_number)
        if force_title or metadata.video_title != expected_title:
            metadata.video_title = expected_title
            save_metadata(metadata_path, metadata)
        return metadata, metadata_path

    context = build_context(story_dir, bible, plan, episode_number)
    metadata = await generator.generate_metadata(context)
    metadata.video_title = serial_video_title(series_title_template, episode_number)
    save_metadata(metadata_path, metadata)
    return metadata, metadata_path


async def schedule_existing_series(
    story_dir: Path,
    series_id: str | None,
    first_date: date | None,
    dry_run: bool,
    series_title_template: str | None,
    force_title: bool,
) -> None:
    story_dir = story_dir.resolve()
    series_id = series_id or infer_series_id(story_dir)
    videos = list_episode_videos(story_dir, series_id)
    if not videos:
        raise FileNotFoundError(f"No videos found for series {series_id} in {story_dir}")

    bible = StoryBible.model_validate_json((story_dir / "story_bible.json").read_text())
    plan = SeriesPlan.model_validate_json((story_dir / "episode_plan.json").read_text())
    series_title_template = series_title_template or f"{bible.title} | Manhwa Recap"
    llm = Gemini(model="gemini-3-flash-preview", temperature=0.7)
    metadata_generator = MetadataGenerator(llm)
    if not dry_run:
        GooglePublisher.assert_youtube_token_present()
    publisher = (
        None
        if dry_run
        else GooglePublisher(
            interactive_auth=False,
            enable_drive=False,
            enable_youtube=True,
        )
    )

    manifest_path = story_dir / "youtube_schedule_manifest.json"
    manifest = load_existing_manifest(manifest_path)
    scheduled_uploads = list(manifest.values())
    first_slot = first_schedule_datetime(first_date)

    for index, (episode_number, video_path) in enumerate(videos):
        if episode_number in manifest:
            logger.info("Episode %d already scheduled; skipping.", episode_number)
            continue

        publish_at = first_slot + timedelta(days=index)
        metadata, metadata_path = await metadata_for_episode(
            story_dir,
            metadata_generator,
            bible,
            plan,
            episode_number,
            series_title_template,
            force_title,
        )

        logger.info(
            "Scheduling episode %d for %s IST: %s",
            episode_number,
            publish_at.strftime("%Y-%m-%d %H:%M"),
            metadata.video_title,
        )

        if dry_run:
            logger.info("Dry run: would upload %s", video_path)
            continue

        assert publisher is not None
        youtube_video = publisher.upload_to_youtube(
            video_path=video_path,
            title=metadata.video_title,
            description=metadata.video_description,
            tags=metadata.tags,
            publish_at=publish_at,
        )
        video_id = youtube_video["id"]
        scheduled_uploads.append(
            ScheduledUpload(
                episode_number=episode_number,
                video_path=str(video_path),
                metadata_path=str(metadata_path),
                youtube_video_id=video_id,
                youtube_url=f"https://www.youtube.com/watch?v={video_id}",
                publish_at=publish_at.isoformat(),
                title=metadata.video_title,
            )
        )
        save_manifest(manifest_path, scheduled_uploads)

    logger.info("Schedule manifest: %s", manifest_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Schedule an already generated series on YouTube one day apart at 9 PM IST."
    )
    parser.add_argument("story_dir", type=Path, help="Path to outputs/<series_timestamp>")
    parser.add_argument(
        "--series",
        default=None,
        help="Series ID; inferred from MP4 names by default",
    )
    parser.add_argument(
        "--first-date",
        type=date.fromisoformat,
        default=None,
        help="First publish date in YYYY-MM-DD. Defaults to the next 9 PM IST slot.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate metadata without uploading",
    )
    parser.add_argument(
        "--title-template",
        default=None,
        help='Stable title base. Example: "My Ex Wife Dumped A Hidden Billionaire | Manhwa Recap"',
    )
    parser.add_argument(
        "--force-title",
        action="store_true",
        help="Rewrite existing metadata JSON titles to the stable Part N format",
    )
    args = parser.parse_args()

    asyncio.run(
        schedule_existing_series(
            story_dir=args.story_dir,
            series_id=args.series,
            first_date=args.first_date,
            dry_run=args.dry_run,
            series_title_template=args.title_template,
            force_title=args.force_title,
        )
    )
