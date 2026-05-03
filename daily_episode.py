from __future__ import annotations

import argparse
import asyncio
import json
import traceback
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from config import settings
from email_notifier import EmailNotifier
from google_publisher import GooglePublisher
from logger import logger
from run_live import run_live


@dataclass
class DailyState:
    series_id: str
    plot: str
    next_episode: int = 1
    last_story_dir: str | None = None
    last_run_at: str | None = None
    last_youtube_url: str | None = None
    last_drive_url: str | None = None


def load_state(path: Path, plot: str, series_id: str) -> DailyState:
    if not path.exists():
        return DailyState(series_id=series_id, plot=plot)

    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("series_id") != series_id:
        logger.info(
            "Series changed from %s to %s; starting at episode 1.", raw.get("series_id"), series_id
        )
        return DailyState(series_id=series_id, plot=plot)

    raw["plot"] = plot
    return DailyState(**raw)


def save_state(path: Path, state: DailyState) -> None:
    path.write_text(json.dumps(asdict(state), indent=2), encoding="utf-8")


def first_publish_result(results: list[Any]) -> tuple[str | None, str | None]:
    if not results:
        return None, None

    result = results[0]
    return result.youtube_url, result.drive_web_view_link or result.drive_file_id


def format_success_email(
    series_id: str,
    episode_number: int,
    state: DailyState,
) -> str:
    return "\n".join(
        [
            "Daily AI Manhwa pipeline completed successfully.",
            "",
            f"Series: {series_id}",
            f"Episode: {episode_number}",
            f"Next episode: {state.next_episode}",
            f"Story directory: {state.last_story_dir}",
            f"YouTube: {state.last_youtube_url or 'Not published'}",
            f"Drive: {state.last_drive_url or 'Not published'}",
            f"Completed at: {state.last_run_at}",
        ]
    )


def format_failure_email(series_id: str, episode_number: int | None, exc: BaseException) -> str:
    return "\n".join(
        [
            "Daily AI Manhwa pipeline failed.",
            "",
            f"Series: {series_id}",
            f"Episode: {episode_number or 'Unknown'}",
            f"Error type: {type(exc).__name__}",
            f"Error: {exc}",
            "",
            "Traceback:",
            traceback.format_exc(),
        ]
    )


def send_notification(notifier: EmailNotifier, subject: str, text: str) -> None:
    try:
        notifier.send(subject, text)
    except Exception as exc:
        logger.error("Email notification failed: %s", exc)


async def run_daily(
    plot: str,
    series_id: str,
    state_path: Path,
    publish: bool,
    start_episode: int | None,
) -> tuple[DailyState, int]:
    state = load_state(state_path, plot=plot, series_id=series_id)
    episode_number = start_episode or state.next_episode

    if publish:
        GooglePublisher.assert_tokens_present()

    logger.info("Daily run generating %s episode %d.", series_id, episode_number)
    result = await run_live(
        plot=plot,
        series_id=series_id,
        num_episodes=episode_number,
        start_episode=episode_number,
        publish=publish,
    )

    if publish and not result["published"]:
        raise RuntimeError(
            "Episode generation did not produce a publish result. Check logs for generation, "
            "Drive upload, or YouTube upload failure details."
        )

    youtube_url, drive_url = first_publish_result(result["published"])
    state.next_episode = episode_number + 1
    state.last_story_dir = str(result["story_dir"])
    state.last_run_at = datetime.now().isoformat(timespec="seconds")
    state.last_youtube_url = youtube_url
    state.last_drive_url = drive_url
    save_state(state_path, state)

    logger.info("Daily state saved to %s. Next episode: %d", state_path, state.next_episode)
    return state, episode_number


def setup_auth() -> None:
    GooglePublisher(interactive_auth=True)
    logger.info("OAuth setup complete. Tokens are ready for daily non-interactive runs.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="End-to-end daily episode pipeline.")
    parser.add_argument(
        "--plot", "-p", default=settings.daily_episode_plot, help="Story plot to create/continue"
    )
    parser.add_argument("--series", "-s", default=settings.daily_series_id, help="Series ID")
    parser.add_argument(
        "--state",
        default="daily_episode_state.json",
        help="Path to the daily scheduler state file",
    )
    parser.add_argument(
        "--skip-publish",
        action="store_true",
        help="Generate only. Daily publishing is enabled by default.",
    )
    parser.add_argument(
        "--setup-auth",
        action="store_true",
        help="Run the one-time browser OAuth flow and create Drive/YouTube tokens.",
    )
    parser.add_argument("--test-email", action="store_true", help="Send a Resend test email.")
    parser.add_argument("--start", type=int, default=None, help="Override the next episode number")
    args = parser.parse_args()

    notifier = EmailNotifier()
    episode_number = args.start

    try:
        if args.test_email:
            send_notification(
                notifier,
                "AI Manhwa email test",
                "Resend notifications are configured for the daily pipeline.",
            )
            logger.info("Test email request completed.")
        elif args.setup_auth:
            setup_auth()
            send_notification(
                notifier,
                "AI Manhwa OAuth setup complete",
                "Drive and YouTube OAuth tokens were created successfully.",
            )
        else:
            if not args.plot or not args.series:
                raise ValueError(
                    "Missing plot or series. Pass --plot/--series or set "
                    "DAILY_EPISODE_PLOT/DAILY_SERIES_ID in .env."
                )

            state, episode_number = asyncio.run(
                run_daily(
                    plot=args.plot,
                    series_id=args.series,
                    state_path=Path(args.state),
                    publish=not args.skip_publish,
                    start_episode=args.start,
                )
            )
            send_notification(
                notifier,
                f"AI Manhwa success: {args.series} episode {episode_number}",
                format_success_email(args.series, episode_number, state),
            )
    except Exception as exc:
        logger.error("Daily pipeline failed: %s", exc)
        send_notification(
            notifier,
            f"AI Manhwa failure: {args.series}",
            format_failure_email(args.series or "unknown", episode_number, exc),
        )
        raise
