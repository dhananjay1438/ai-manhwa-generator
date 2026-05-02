import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List

import whisper_timestamped as whisper

from core.image.base import BaseImageGenerator
from core.audio.base import BaseAudioGenerator
from logger import logger


class AssetFactory:
    def __init__(
        self,
        image_generator: BaseImageGenerator,
        audio_generator: BaseAudioGenerator,
        enable_whisper: bool = False,
    ):
        self.image_generator = image_generator
        self.audio_generator = audio_generator
        self.enable_whisper = enable_whisper
        self.whisper_model = None

    def _get_whisper_model(self):
        if self.whisper_model is None and self.enable_whisper:
            # Use small/base for speed locally
            self.whisper_model = whisper.load_model("base")
        return self.whisper_model

    def _transcribe_audio(self, audio_path: Path, output_json_path: Path):
        """Passes audio through whisper-timestamped to get word-level boundaries."""
        if not self.enable_whisper:
            return None

        if output_json_path.exists():
            logger.info("Skipping transcription %s, already exists.", output_json_path)
            return output_json_path

        model = self._get_whisper_model()
        audio = whisper.load_audio(str(audio_path))
        result = whisper.transcribe(model, audio, language="en")

        words_data = []
        for segment in result.get("segments", []):
            for word in segment.get("words", []):
                words_data.append(
                    {"word": word["text"], "start_time": word["start"], "end_time": word["end"]}
                )

        with output_json_path.open("w", encoding="utf-8") as f:
            json.dump(words_data, f, indent=4)

        return output_json_path

    async def generate_assets(
        self, episode_id: str, compiled_prompts: List[Dict[str, Any]], script_text: str, base_dir: Path = None
    ):
        """Main orchestrator for Module 2."""
        if base_dir is None:
            base_dir = Path("./assets") / f"ep_{episode_id}"
        img_dir = base_dir / "images"
        img_dir.mkdir(parents=True, exist_ok=True)

        audio_path = base_dir / "audio.mp3"
        transcription_path = base_dir / "transcription.json"

        # 1. Start audio generation and transcription
        async def process_audio_and_transcribe():
            await self.audio_generator.generate_audio(script_text, str(audio_path))

            if self.enable_whisper:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, self._transcribe_audio, audio_path, transcription_path
                )

        # 2. Start image generation tasks
        image_tasks = []
        for prompt_data in compiled_prompts:
            panel_id = prompt_data["panel_id"]
            prompt = prompt_data["prompt"]
            output_path = img_dir / f"panel_{panel_id:03d}.png"
            task = self.image_generator.generate_image(prompt, str(output_path))
            image_tasks.append(task)

        # 3. Run all concurrently
        await asyncio.gather(process_audio_and_transcribe(), *image_tasks)

        return {
            "image_dir": str(img_dir),
            "audio_path": str(audio_path),
            "transcription_path": str(transcription_path) if self.enable_whisper else None,
        }
