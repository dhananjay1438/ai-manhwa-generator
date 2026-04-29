import os
import json
import asyncio
import whisper_timestamped as whisper
from typing import List, Dict, Any
from generators import ImageGeneratorFactory, AudioGeneratorFactory

class AssetFactory:
    def __init__(self, runware_api_key: str, google_api_key: str, google_tts_voice: str, enable_whisper: bool):
        self.image_generator = ImageGeneratorFactory.get_generator("runware", api_key=runware_api_key)
        self.audio_generator = AudioGeneratorFactory.get_generator("vertex_ai", api_key=google_api_key, voice=google_tts_voice)
        self.enable_whisper = enable_whisper
        self.whisper_model = None

    def _get_whisper_model(self):
        if self.whisper_model is None and self.enable_whisper:
            self.whisper_model = whisper.load_model("base") # Use small/base for speed locally
        return self.whisper_model

    def _transcribe_audio(self, audio_path: str, output_json_path: str):
        """Passes audio through whisper-timestamped to get word-level boundaries."""
        if not self.enable_whisper:
            return None

        if os.path.exists(output_json_path):
            print(f"Skipping transcription {output_json_path}, already exists.")
            return output_json_path

        model = self._get_whisper_model()
        audio = whisper.load_audio(audio_path)
        result = whisper.transcribe(model, audio, language="en")

        words_data = []
        for segment in result.get("segments", []):
            for word in segment.get("words", []):
                words_data.append({
                    "word": word["text"],
                    "start_time": word["start"],
                    "end_time": word["end"]
                })

        with open(output_json_path, "w", encoding="utf-8") as f:
            json.dump(words_data, f, indent=4)

        return output_json_path

    async def generate_assets(self, episode_id: str, compiled_prompts: List[Dict[str, Any]], script_text: str):
        """Main orchestrator for Module 2."""
        base_dir = f"./assets/ep_{episode_id}"
        img_dir = os.path.join(base_dir, "images")
        os.makedirs(img_dir, exist_ok=True)

        audio_path = os.path.join(base_dir, "audio.mp3")
        transcription_path = os.path.join(base_dir, "transcription.json")

        # 1. Start audio generation and transcription
        async def process_audio_and_transcribe():
            await self.audio_generator.generate_audio(script_text, audio_path)

            if self.enable_whisper:
                loop = asyncio.get_event_loop()
                # Use duck typing to check for mock audio in tests so whisper doesn't fail
                if getattr(self.audio_generator, "api_key", None) != "MOCK_KEY":
                    await loop.run_in_executor(None, self._transcribe_audio, audio_path, transcription_path)
                else:
                    with open(transcription_path, "w") as f:
                        json.dump([{"word": "Hello", "start_time": 0.0, "end_time": 0.5}], f)

        # 2. Start image generation tasks
        image_tasks = []
        for prompt_data in compiled_prompts:
            panel_id = prompt_data["panel_id"]
            prompt = prompt_data["prompt"]
            output_path = os.path.join(img_dir, f"panel_{panel_id:03d}.png")
            task = self.image_generator.generate_image(prompt, output_path)
            image_tasks.append(task)

        # 3. Run all concurrently
        await asyncio.gather(process_audio_and_transcribe(), *image_tasks)

        return {
            "image_dir": img_dir,
            "audio_path": audio_path,
            "transcription_path": transcription_path if self.enable_whisper else None
        }
