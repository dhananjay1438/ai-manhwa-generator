import asyncio
import os
import shutil
from main import run_pipeline
from state_manager import StateManager
from config import settings
from PIL import Image
import subprocess
from generators import RunwareImageGenerator, VertexAITTSGenerator

async def mock_test():
    print("Setting up test environment...")

    # 1. Initialize a mock state
    sm = StateManager()
    sm.update_state("style_token", "Manhwa panel, cel shaded, bold outlines, webtoon style, --ar 9:16")
    sm.update_state("character_registry", {
        "Arthur": "tall, dark hair, glowing red eyes, wearing dark armor"
    })

    # 2. Define a mock script that fits our models
    mock_script = {
        "episode_number": 1,
        "narrator_script": "The kingdom was burning. Arthur stood alone.",
        "visual_prompts": [
            {
                "panel_id": 1,
                "characters_in_frame": ["Arthur"],
                "raw_action_description": "Arthur looking out over the burning city."
            },
            {
                "panel_id": 2,
                "characters_in_frame": [],
                "raw_action_description": "A wide shot of the crumbling castle."
            }
        ],
        "cliffhanger_ending": "A shadow emerged from the flames..."
    }

    series_id = "test_series"
    episode_id = f"{series_id}_1"

    def cleanup():
        assets_dir = f"./assets/ep_{episode_id}"
        if os.path.exists(assets_dir):
            shutil.rmtree(assets_dir)

        final_video = f"ep_{episode_id}_final.mp4"
        if os.path.exists(final_video):
            os.remove(final_video)

    # Let's override the Generator methods temporarily for the test so it writes real dummy files
    original_generate_image = RunwareImageGenerator.generate_image

    async def mock_generate_image(self, prompt, output_path):
        # Create a real, blank 512x896 image
        img = Image.new('RGB', (512, 896), color = 'red')
        img.save(output_path)
        return output_path

    RunwareImageGenerator.generate_image = mock_generate_image

    # For audio, FFmpeg needs a real audio file. Let's create a silent mp3 using ffmpeg.
    original_generate_audio = VertexAITTSGenerator.generate_audio

    async def mock_generate_audio(self, text, output_path):
        subprocess.run(['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', '3', '-q:a', '9', '-acodec', 'libmp3lame', output_path, '-y'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_path

    VertexAITTSGenerator.generate_audio = mock_generate_audio

    # Test WITH Whisper
    print("\n--- Running pipeline (Whisper Enabled) ---")
    settings.enable_whisper = True
    cleanup()
    await run_pipeline(series_id, mock_script)
    assert os.path.exists(f"ep_{episode_id}_final.mp4"), "Final video not found for Whisper test."

    # Test WITHOUT Whisper
    print("\n--- Running pipeline (Whisper Disabled) ---")
    settings.enable_whisper = False
    cleanup()
    await run_pipeline(series_id, mock_script)
    assert os.path.exists(f"ep_{episode_id}_final.mp4"), "Final video not found for Non-Whisper test."

    print("\nAll tests passed successfully!")

if __name__ == "__main__":
    asyncio.run(mock_test())
