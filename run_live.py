import argparse
import asyncio
from datetime import datetime
from pathlib import Path

from config import settings
from core.llm.gemini import Gemini
from core.story.bible_generator import BibleGenerator
from core.story.chapter_planner import ChapterPlanner
from core.story.chapter_writer import ChapterWriter
from core.story.episode_planner import EpisodePlanner
from google_publisher import GooglePublisher
from logger import logger
from main import run_pipeline
from models import EpisodeScript, VisualPrompt
from state_manager import StateManager
from youtube_metadata import (
    EpisodeMetadataContext,
    MetadataGenerator,
    save_metadata,
    serial_video_title,
)


def stitch_chapters(
    chapter_scripts, episode_number: int, episode_title: str, hook_line: str, cliffhanger: str
) -> EpisodeScript:
    """Combines multiple ChapterScripts into a single EpisodeScript."""
    all_narration = []
    all_panels = []
    panel_counter = 1

    for ch in chapter_scripts:
        all_narration.append(ch.narration)

        for vp in ch.visual_prompts:
            # Re-number panels sequentially across the whole episode
            all_panels.append(
                VisualPrompt(
                    panel_id=panel_counter,
                    characters_in_frame=vp.characters_in_frame,
                    raw_action_description=vp.raw_action_description,
                    camera_angle=vp.camera_angle,
                )
            )
            panel_counter += 1

    return EpisodeScript(
        episode_number=episode_number,
        title=episode_title,
        hook_line=hook_line,
        narrator_script="\n\n".join(all_narration),
        visual_prompts=all_panels,
        cliffhanger_ending=cliffhanger,
    )


async def run_live(
    plot: str,
    series_id: str,
    num_episodes: int = 1,
    start_episode: int = 1,
    publish: bool = False,
):
    logger.info("=" * 60)
    logger.info("AI MANHWA GENERATOR — Long-Form Chapter Pipeline")
    logger.info("=" * 60)
    logger.info("Plot: %s", plot)
    logger.info("Series: %s | Episodes: %d", series_id, num_episodes)
    logger.info("=" * 60)

    # Initialize
    sm = StateManager()
    sm.update_state(
        "style_token",
        "Korean manhwa webtoon art style, cel-shaded coloring, bold black outlines, "
        "dramatic lighting and shadows, expressive anime-style eyes, vibrant saturated colors, "
        "vertical panel composition, manhwa panel --ar 9:16",
    )

    llm = Gemini(model="gemini-3-flash-preview", temperature=0.9)

    # Output directory for story artifacts
    outputs_dir = Path("outputs")
    outputs_dir.mkdir(exist_ok=True)

    if start_episode == 1:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        story_dir = outputs_dir / f"{series_id}_{timestamp}"
        story_dir.mkdir(parents=True, exist_ok=True)
    else:
        existing = sorted([d for d in outputs_dir.glob(f"{series_id}_*") if d.is_dir()])
        if existing:
            story_dir = existing[-1]
            logger.info("Resuming in directory: %s", story_dir)
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            story_dir = outputs_dir / f"{series_id}_{timestamp}"
            story_dir.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────────
    # STAGE 1: Generate Story Bible
    # ──────────────────────────────────────────────
    bible_path = story_dir / "story_bible.json"

    if bible_path.exists():
        logger.info("Loading existing Story Bible from %s", bible_path)
        from core.story.models import StoryBible

        bible = StoryBible.model_validate_json(bible_path.read_text())
    else:
        bible_gen = BibleGenerator(llm=llm)
        bible = await bible_gen.generate(plot)

        bible_path.write_text(bible.model_dump_json(indent=2))
        logger.info("Story Bible saved to %s", bible_path)

    # Register characters from bible
    char_registry = {}
    for char in bible.characters:
        char_registry[char.name] = char.appearance
    sm.update_state("character_registry", char_registry)

    logger.info("Title: %s", bible.title)
    logger.info("Logline: %s", bible.logline)
    logger.info("Characters: %s", [c.name for c in bible.characters])
    logger.info("Settings: %s", [s.name for s in bible.settings])
    logger.info("Story Beats: %d", len(bible.plot_beats))

    # ──────────────────────────────────────────────
    # STAGE 2: Plan Episodes
    # ──────────────────────────────────────────────
    plan_path = story_dir / "episode_plan.json"
    plan = None

    if plan_path.exists():
        logger.info("Loading existing Episode Plan from %s", plan_path)
        from core.story.models import SeriesPlan

        plan = SeriesPlan.model_validate_json(plan_path.read_text())

        if len(plan.episodes) < num_episodes:
            logger.info(
                "Existing plan only has %d episodes, but %d requested. Re-planning...",
                len(plan.episodes),
                num_episodes,
            )
            plan = None

    if plan is None:
        planner = EpisodePlanner(llm=llm)
        plan = await planner.plan(bible, target_episodes=num_episodes)

        plan_path.write_text(plan.model_dump_json(indent=2))
        logger.info("Episode Plan saved to %s", plan_path)

    # ──────────────────────────────────────────────
    # STAGE 3: Chapter-based Writing + Production
    # ──────────────────────────────────────────────
    chapter_planner = ChapterPlanner(llm=llm)
    chapter_writer = ChapterWriter(llm=llm)
    previous_cliffhanger = ""
    publisher = GooglePublisher(interactive_auth=False) if publish else None
    published_results = []

    for ep_plan in plan.episodes:
        if ep_plan.episode_number < start_episode:
            # Load previous cliffhanger for continuity
            script_path = story_dir / f"episode_{ep_plan.episode_number:02d}_script.json"
            if script_path.exists():
                prev_script = EpisodeScript.model_validate_json(script_path.read_text())
                previous_cliffhanger = prev_script.cliffhanger_ending
            continue

        logger.info("")
        logger.info("━" * 50)
        logger.info("EPISODE %d: %s", ep_plan.episode_number, ep_plan.title)
        logger.info("━" * 50)

        script_path = story_dir / f"episode_{ep_plan.episode_number:02d}_script.json"

        if script_path.exists():
            logger.info("Loading existing script from %s", script_path)
            script = EpisodeScript.model_validate_json(script_path.read_text())
        else:
            # STAGE 3a: Plan chapters for this episode
            ch_plan_path = story_dir / f"episode_{ep_plan.episode_number:02d}_chapter_plan.json"

            if ch_plan_path.exists():
                logger.info("Loading existing chapter plan from %s", ch_plan_path)
                from core.story.models import EpisodeChapterPlan

                ch_plan = EpisodeChapterPlan.model_validate_json(ch_plan_path.read_text())
            else:
                ch_plan = await chapter_planner.plan(bible, ep_plan)
                ch_plan_path.write_text(ch_plan.model_dump_json(indent=2))
                logger.info("Chapter plan saved to %s", ch_plan_path)

            # STAGE 3b: Write each chapter sequentially
            chapter_scripts = []
            prev_closing = previous_cliffhanger  # continuity from last episode

            for ch in ch_plan.chapters:
                ch_script_path = (
                    story_dir
                    / f"episode_{ep_plan.episode_number:02d}_chapter_{ch.chapter_number:02d}.json"
                )

                if ch_script_path.exists():
                    logger.info(
                        "   Loading existing Chapter %d from %s", ch.chapter_number, ch_script_path
                    )
                    from models import ChapterScript

                    ch_script = ChapterScript.model_validate_json(ch_script_path.read_text())
                else:
                    ch_script = await chapter_writer.write(
                        bible=bible,
                        chapter_plan=ch,
                        episode_number=ep_plan.episode_number,
                        episode_title=ep_plan.title,
                        total_chapters=ch_plan.total_chapters,
                        previous_closing=prev_closing,
                    )
                    ch_script_path.write_text(ch_script.model_dump_json(indent=2))
                    logger.info("   Chapter %d saved to %s", ch.chapter_number, ch_script_path)

                prev_closing = ch_script.closing_line
                chapter_scripts.append(ch_script)

            # STAGE 3c: Stitch chapters into final episode script
            script = stitch_chapters(
                chapter_scripts,
                episode_number=ep_plan.episode_number,
                episode_title=ep_plan.title,
                hook_line=ep_plan.opening_hook,
                cliffhanger=ep_plan.cliffhanger_ending,
            )

            script_path.write_text(script.model_dump_json(indent=2))
            logger.info("Stitched episode script saved to %s", script_path)

        previous_cliffhanger = script.cliffhanger_ending

        logger.info("Hook: %s", script.hook_line)
        logger.info("Panels: %d", len(script.visual_prompts))
        logger.info("Narration: %d words", len(script.narrator_script.split()))
        logger.info("Cliffhanger: %s", script.cliffhanger_ending)

        # Stage 4: Production pipeline
        episode_id = f"{series_id}_{ep_plan.episode_number}"
        script_data = script.model_dump()

        try:
            await run_pipeline(series_id, script_data, output_dir=story_dir)
            final_video = story_dir / f"ep_{episode_id}_final.mp4"
            if final_video.exists():
                logger.info(
                    "✅ Episode %d complete: %s", ep_plan.episode_number, final_video.resolve()
                )
                if publisher:
                    metadata_path = (
                        story_dir / f"episode_{ep_plan.episode_number:02d}_youtube_metadata.json"
                    )
                    if metadata_path.exists():
                        from youtube_metadata import YouTubeMetadata

                        metadata = YouTubeMetadata.model_validate_json(
                            metadata_path.read_text(encoding="utf-8")
                        )
                    else:
                        chapter_plan_path = (
                            story_dir / f"episode_{ep_plan.episode_number:02d}_chapter_plan.json"
                        )
                        chapters = []
                        if chapter_plan_path.exists():
                            from core.story.models import EpisodeChapterPlan

                            chapter_plan = EpisodeChapterPlan.model_validate_json(
                                chapter_plan_path.read_text(encoding="utf-8")
                            )
                            chapters = [chapter.title for chapter in chapter_plan.chapters]

                        metadata = await MetadataGenerator(llm).generate_metadata(
                            EpisodeMetadataContext(
                                series_title=bible.title,
                                series_logline=bible.logline,
                                episode_number=ep_plan.episode_number,
                                episode_title=script.title or ep_plan.title,
                                episode_summary=ep_plan.summary,
                                hook_line=script.hook_line,
                                cliffhanger_ending=script.cliffhanger_ending,
                                chapters=chapters,
                            )
                        )
                        metadata.video_title = serial_video_title(
                            f"{bible.title} | Manhwa Recap", ep_plan.episode_number
                        )
                        save_metadata(metadata_path, metadata)

                    description = "\n\n".join(
                        [
                            metadata.video_description,
                            f"Series: {series_id}",
                            f"Episode: {ep_plan.episode_number}",
                        ]
                    )
                    result = publisher.publish_episode(
                        video_path=final_video,
                        series_id=series_id,
                        episode_number=ep_plan.episode_number,
                        title=metadata.video_title,
                        description=description,
                        tags=metadata.tags,
                        append_episode_suffix=False,
                    )
                    published_results.append(result)
                    logger.info(
                        "Drive upload: %s", result.drive_web_view_link or result.drive_file_id
                    )
                    logger.info("YouTube upload: %s", result.youtube_url)
            else:
                logger.error(
                    "❌ Episode %d: Video not found after pipeline", ep_plan.episode_number
                )
        except Exception as e:
            logger.error("❌ Episode %d CRASHED: %s", ep_plan.episode_number, e)
            import traceback

            traceback.print_exc()
            continue

    logger.info("")
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE — All episodes generated!")
    logger.info("Story artifacts: %s", story_dir.resolve())
    logger.info("=" * 60)
    return {"story_dir": story_dir, "published": published_results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Manhwa Generator — Long-Form Chapter Pipeline")
    parser.add_argument(
        "--plot",
        "-p",
        type=str,
        required=True,
        help="The story plot to generate.",
    )
    parser.add_argument("--series", "-s", type=str, default="revenge_series", help="Series ID")
    parser.add_argument(
        "--episodes", "-e", type=int, default=1, help="Number of episodes to generate (default: 1)"
    )
    parser.add_argument(
        "--start", type=int, default=1, help="Start from episode N (skips earlier ones)"
    )
    parser.add_argument(
        "--publish", action="store_true", help="Upload completed episodes to Drive and YouTube"
    )

    args = parser.parse_args()

    settings.enable_whisper = False

    asyncio.run(run_live(args.plot, args.series, args.episodes, args.start, publish=args.publish))
