import asyncio
import os
import shutil
from main import run_pipeline
from state_manager import StateManager
from PIL import Image

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

    # Clean up previous test runs if they exist
    assets_dir = f"./assets/ep_{episode_id}"
    if os.path.exists(assets_dir):
        shutil.rmtree(assets_dir)

    final_video = f"ep_{episode_id}_final.mp4"
    if os.path.exists(final_video):
        os.remove(final_video)

    # We need to preemptively create some "mock" actual image files because the
    # current mocked AssetFactory just writes "mock_image_data" string,
    # but FFmpeg requires actual valid images to build the video.

    # Let's override the AssetFactory mock temporarily for the test so it writes real dummy PNGs
    from asset_factory import AssetFactory

    original_generate_image = AssetFactory._generate_image

    async def mock_generate_image(self, session, prompt, output_path):
        # Create a real, blank 512x896 image
        img = Image.new('RGB', (512, 896), color = 'red')
        img.save(output_path)
        return output_path

    AssetFactory._generate_image = mock_generate_image

    # For audio, FFmpeg needs a real audio file. Let's create a silent mp3 using ffmpeg.
    original_generate_audio = AssetFactory._generate_audio

    async def mock_generate_audio(self, session, text, output_path):
        import subprocess
        subprocess.run(['ffmpeg', '-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=mono', '-t', '3', '-q:a', '9', '-acodec', 'libmp3lame', output_path, '-y'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return output_path

    AssetFactory._generate_audio = mock_generate_audio

    # Run the pipeline
    print("Running pipeline...")
    await run_pipeline(series_id, mock_script)

    # Verify outputs
    assert os.path.exists(final_video), f"Final video not found: {final_video}"
    print(f"Test passed! Video generated successfully at {final_video}")

if __name__ == "__main__":
    asyncio.run(mock_test())
