import asyncio
import shutil
import subprocess
from pathlib import Path

from PIL import Image

from config import settings
from generators import RunwareImageGenerator, VertexAITTSGenerator
from logger import logger
from main import run_pipeline
from state_manager import StateManager


async def mock_test():
    logger.info("Setting up test environment...")

    # 1. Initialize a mock state
    sm = StateManager()
    sm.update_state(
        "style_token", "Manhwa panel, cel shaded, bold outlines, webtoon style, --ar 9:16"
    )
    sm.update_state(
        "character_registry", {"Arthur": "tall, dark hair, glowing red eyes, wearing dark armor"}
    )

    # 2. Define a mock script that fits our models
    mock_script = {
        "episode_number": 1,
        "narrator_script": "The kingdom was burning. Arthur stood alone.",
        "visual_prompts": [
            {
                "panel_id": 1,
                "characters_in_frame": ["Arthur"],
                "raw_action_description": "Arthur looking out over the burning city.",
            },
            {
                "panel_id": 2,
                "characters_in_frame": [],
                "raw_action_description": "A wide shot of the crumbling castle.",
            },
        ],
        "cliffhanger_ending": "A shadow emerged from the flames...",
    }

    series_id = "test_series"
    episode_id = f"{series_id}_1"

    def cleanup():
        assets_dir = Path("./assets") / f"ep_{episode_id}"
        if assets_dir.exists():
            shutil.rmtree(assets_dir)

        final_video = Path(f"ep_{episode_id}_final.mp4")
        if final_video.exists():
            final_video.unlink()

    # Let's override the Generator methods temporarily for the test
    async def mock_generate_image(_self, _prompt, output_path):
        # Create a real, blank 512x896 image
        img = Image.new("RGB", (512, 896), color="red")
        img.save(output_path)
        return output_path

    RunwareImageGenerator.generate_image = mock_generate_image

    # For audio, FFmpeg needs a real audio file.
    async def mock_generate_audio(_self, _text, output_path):
        subprocess.run(
            [
                "ffmpeg",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=44100:cl=mono",
                "-t",
                "3",
                "-q:a",
                "9",
                "-acodec",
                "libmp3lame",
                output_path,
                "-y",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return output_path

    VertexAITTSGenerator.generate_audio = mock_generate_audio

    # Test WITH Whisper
    logger.info("--- Running pipeline (Whisper Enabled) ---")
    settings.enable_whisper = True
    cleanup()
    await run_pipeline(series_id, mock_script)
    assert Path(f"ep_{episode_id}_final.mp4").exists(), "Final video not found for Whisper test."

    # Test WITHOUT Whisper
    logger.info("--- Running pipeline (Whisper Disabled) ---")
    settings.enable_whisper = False
    cleanup()
    await run_pipeline(series_id, mock_script)
    assert Path(f"ep_{episode_id}_final.mp4").exists(), (
        "Final video not found for Non-Whisper test."
    )

    logger.info("All tests passed successfully!")


if __name__ == "__main__":
    asyncio.run(mock_test())
